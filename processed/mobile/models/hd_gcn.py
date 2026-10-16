"""HD-GCN architecture bundled for reproducible ExecuTorch export.

This is kept compatible with the architecture that produced the existing
HandGCN checkpoints. Changing layer names or tensor shapes breaks strict
checkpoint loading and therefore requires a new model format version.
"""

from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn
import torch.nn.functional as F

from .base import SignLanguageModel, initialize_kaiming


def normalize_adjacency(adjacency: torch.Tensor) -> torch.Tensor:
    """Return D^(-1/2) A D^(-1/2)."""
    degree = adjacency.sum(dim=1)
    degree_inv_sqrt = torch.pow(degree + 1e-6, -0.5)
    degree_inv_sqrt[torch.isinf(degree_inv_sqrt)] = 0.0
    return torch.diag(degree_inv_sqrt) @ adjacency @ torch.diag(degree_inv_sqrt)


class DistanceAwareGCNLayer(nn.Module):
    """Graph convolution with one projection per hop distance."""

    def __init__(self, in_channels: int, out_channels: int, max_distance: int = 2) -> None:
        super().__init__()
        self.max_distance = max_distance
        self.out_channels = out_channels
        self.linear_layers = nn.ModuleList(
            nn.Linear(in_channels, out_channels) for _ in range(max_distance + 1)
        )
        self.bn = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)

        for linear in self.linear_layers:
            nn.init.kaiming_normal_(linear.weight, nonlinearity="relu")
            if linear.bias is not None:
                nn.init.zeros_(linear.bias)

    def forward(self, x: torch.Tensor, adjacencies: List[torch.Tensor]) -> torch.Tensor:
        batch_size, node_count, _ = x.shape
        weights = torch.cat([linear.weight for linear in self.linear_layers], dim=0)
        biases = torch.cat([linear.bias for linear in self.linear_layers], dim=0)
        projections = F.linear(x, weights, biases).split(self.out_channels, dim=-1)

        output: Optional[torch.Tensor] = None
        for distance in range(self.max_distance + 1):
            contribution = torch.matmul(adjacencies[distance], projections[distance])
            output = contribution if output is None else output + contribution

        if output is None:  # Defensive only; max_distance is non-negative.
            raise RuntimeError("HD-GCN produced no graph-convolution output")
        output = self.bn(output.reshape(batch_size * node_count, -1)).reshape(
            batch_size, node_count, -1
        )
        return self.relu(output)


class HandGCNModel(SignLanguageModel):
    """Hierarchical distance-aware GCN for two MediaPipe hands."""

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        num_nodes: int = 42,
        gcn_channels: int = 64,
        num_gcn_layers: int = 2,
        temporal_channels: int = 128,
        dropout: float = 0.3,
        max_distance: int = 2,
        **_: Any,
    ) -> None:
        super().__init__(input_dim, output_dim, name="HandGCN")
        self.num_nodes = num_nodes
        self.gcn_channels = gcn_channels
        self.num_gcn_layers = num_gcn_layers
        self.temporal_channels = temporal_channels
        self.dropout_rate = dropout
        self.max_distance = max_distance

        fine_adjacencies = self._build_distance_adjacencies_fine(max_distance)
        for distance, adjacency in enumerate(fine_adjacencies):
            self.register_buffer(f"fine_adj_d{distance}", adjacency)

        part_adjacencies = self._build_distance_adjacencies_part(max_distance)
        for distance, adjacency in enumerate(part_adjacencies):
            self.register_buffer(f"part_adj_d{distance}", adjacency)

        self.register_buffer("hierarchical_pooling_matrix", self._build_pooling_matrix())
        self.input_projection = nn.Linear(input_dim // self.num_nodes, gcn_channels)
        self.fine_gcns = nn.ModuleList(
            DistanceAwareGCNLayer(gcn_channels, gcn_channels, max_distance)
            for _ in range(num_gcn_layers)
        )
        self.part_gcns = nn.ModuleList(
            [DistanceAwareGCNLayer(gcn_channels, gcn_channels, max_distance)]
        )
        self.temporal_conv1 = nn.Conv1d(
            gcn_channels, temporal_channels, kernel_size=3, padding=1
        )
        self.temporal_conv2 = nn.Conv1d(
            temporal_channels, temporal_channels, kernel_size=3, padding=1
        )
        self.attention = nn.Sequential(
            nn.Linear(temporal_channels, temporal_channels // 2),
            nn.ReLU(inplace=True),
            nn.Linear(temporal_channels // 2, 1),
            nn.Softmax(dim=1),
        )
        self.classifier = nn.Sequential(
            nn.Linear(temporal_channels, temporal_channels // 2),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(temporal_channels // 2, output_dim),
        )
        initialize_kaiming(self)

    @staticmethod
    def _get_shortest_paths(node_count: int, edges: List[tuple[int, int]]) -> torch.Tensor:
        distances = torch.full((node_count, node_count), float("inf"))
        for node in range(node_count):
            distances[node, node] = 0
        for start, end in edges:
            distances[start, end] = 1
            distances[end, start] = 1
        for intermediate in range(node_count):
            for start in range(node_count):
                for end in range(node_count):
                    candidate = distances[start, intermediate] + distances[intermediate, end]
                    if distances[start, end] > candidate:
                        distances[start, end] = candidate
        return distances

    def _build_distance_adjacencies_fine(self, max_distance: int) -> List[torch.Tensor]:
        one_hand_edges = [
            (0, 1), (1, 2), (2, 3), (3, 4),
            (0, 5), (5, 6), (6, 7), (7, 8),
            (0, 9), (9, 10), (10, 11), (11, 12),
            (0, 13), (13, 14), (14, 15), (15, 16),
            (0, 17), (17, 18), (18, 19), (19, 20),
        ]
        both_hands = [edge for start, end in one_hand_edges for edge in ((start, end), (start + 21, end + 21))]
        distances = self._get_shortest_paths(42, both_hands)
        return [normalize_adjacency((distances == distance).float()) for distance in range(max_distance + 1)]

    def _build_distance_adjacencies_part(self, max_distance: int) -> List[torch.Tensor]:
        one_hand_edges = [(0, 1), (0, 2), (0, 3), (0, 4), (0, 5)]
        both_hands = [edge for start, end in one_hand_edges for edge in ((start, end), (start + 6, end + 6))]
        distances = self._get_shortest_paths(12, both_hands)
        return [normalize_adjacency((distances == distance).float()) for distance in range(max_distance + 1)]

    @staticmethod
    def _build_pooling_matrix() -> torch.Tensor:
        pooling = torch.zeros(12, 42)
        pooling[0, 0] = 1.0
        pooling[1, 1:5] = 0.25
        pooling[2, 5:9] = 0.25
        pooling[3, 9:13] = 0.25
        pooling[4, 13:17] = 0.25
        pooling[5, 17:21] = 0.25
        pooling[6, 21] = 1.0
        pooling[7, 22:26] = 0.25
        pooling[8, 26:30] = 0.25
        pooling[9, 30:34] = 0.25
        pooling[10, 34:38] = 0.25
        pooling[11, 38:42] = 0.25
        return pooling

    def encode(self, x_btd: torch.Tensor) -> torch.Tensor:
        if x_btd.ndim != 3:
            raise RuntimeError(f"Expected [B,T,D], got {tuple(x_btd.shape)}")
        batch_size, sequence_length, feature_dim = x_btd.shape
        features_per_node = feature_dim // self.num_nodes
        graph = x_btd.reshape(batch_size * sequence_length, self.num_nodes, features_per_node)
        graph = self.input_projection(graph)

        fine_adjacencies = [
            getattr(self, f"fine_adj_d{distance}")
            for distance in range(self.max_distance + 1)
        ]
        for layer in self.fine_gcns:
            graph = layer(graph, fine_adjacencies)

        parts = torch.matmul(self.hierarchical_pooling_matrix, graph)
        part_adjacencies = [
            getattr(self, f"part_adj_d{distance}")
            for distance in range(self.max_distance + 1)
        ]
        for layer in self.part_gcns:
            parts = layer(parts, part_adjacencies)

        temporal = parts.mean(dim=1).reshape(batch_size, sequence_length, self.gcn_channels)
        temporal = temporal.permute(0, 2, 1)
        temporal = torch.relu(self.temporal_conv1(temporal))
        temporal = torch.relu(self.temporal_conv2(temporal))
        attended = temporal.permute(0, 2, 1)
        return (attended * self.attention(attended)).sum(dim=1)

    def forward(self, x_btd: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.encode(x_btd))

    @classmethod
    def from_config(
        cls,
        input_dim: int,
        output_dim: int,
        config: Optional[Dict[str, Any]] = None,
    ) -> "HandGCNModel":
        values = config or {}
        return cls(
            input_dim=input_dim,
            output_dim=output_dim,
            num_nodes=values.get("num_nodes", 42),
            gcn_channels=values.get("gcn_channels", 64),
            num_gcn_layers=values.get("num_gcn_layers", 2),
            temporal_channels=values.get("temporal_channels", 128),
            dropout=values.get("dropout", 0.3),
            max_distance=values.get("max_distance", 2),
        )

    def get_config(self) -> Dict[str, Any]:
        return {
            "model": "HandGCN",
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "num_nodes": self.num_nodes,
            "gcn_channels": self.gcn_channels,
            "num_gcn_layers": self.num_gcn_layers,
            "temporal_channels": self.temporal_channels,
            "dropout": self.dropout_rate,
            "max_distance": self.max_distance,
        }
