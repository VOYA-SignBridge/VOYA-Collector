"""Hierarchical Distance-aware Graph Convolutional Network for sign language recognition"""

from typing import Any, Dict, Optional, List

import torch
import torch.nn as nn
import torch.nn.functional as F

from .base import SignLanguageModel, initialize_kaiming


def normalize_adjacency(adj: torch.Tensor) -> torch.Tensor:
    """Symmetric normalization: D^(-1/2) * A * D^(-1/2)"""
    degree = adj.sum(dim=1)
    degree_inv_sqrt = torch.pow(degree + 1e-6, -0.5)
    degree_inv_sqrt[torch.isinf(degree_inv_sqrt)] = 0.0
    degree_mat_inv_sqrt = torch.diag(degree_inv_sqrt)
    return degree_mat_inv_sqrt @ adj @ degree_mat_inv_sqrt


class DistanceAwareGCNLayer(nn.Module):
    """
    Distance-aware Graph Convolutional Layer.
    Uses multiple adjacency matrices for different hop distances.
    """
    def __init__(self, in_channels: int, out_channels: int, max_distance: int = 2):
        super().__init__()
        self.max_distance = max_distance
        self.out_channels = out_channels
        # We need a linear projection for each distance matrix
        self.linear_layers = nn.ModuleList([
            nn.Linear(in_channels, out_channels) for _ in range(max_distance + 1)
        ])
        self.bn = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)

        for linear in self.linear_layers:
            nn.init.kaiming_normal_(linear.weight, nonlinearity='relu')
            if linear.bias is not None:
                nn.init.zeros_(linear.bias)

    def forward(self, x: torch.Tensor, adjs: List[torch.Tensor]) -> torch.Tensor:
        """
        Args:
            x: [B, N, in_channels]
            adjs: List of normalized adjacency matrices [N, N], length = max_distance + 1
        """
        B, N, C = x.shape

        # Gộp các phép chiếu theo khoảng cách thành MỘT gemm rồi mới tách.
        # Trọng số vẫn nằm ở từng nn.Linear (state_dict không đổi), chỉ ghép lại
        # lúc forward — rẻ vì ma trận trọng số bé, trong khi x là [batch*T, N, C].
        weight = torch.cat([lin.weight for lin in self.linear_layers], dim=0)
        bias = torch.cat([lin.bias for lin in self.linear_layers], dim=0)
        projections = F.linear(x, weight, bias).split(self.out_channels, dim=-1)

        out: Optional[torch.Tensor] = None
        for d in range(self.max_distance + 1):
            # A_d @ x_proj. matmul broadcasts [N,N] over the batch, nên không
            # phải expand adjacency thành B bản rồi bmm như trước.
            contrib = torch.matmul(adjs[d], projections[d])
            out = contrib if out is None else out + contrib

        # BatchNorm1d thống kê theo channel: gộp [B,N,C] -> [B*N,C] cho ra đúng
        # cùng mean/var với đường [B,C,N], nhưng bỏ được 2 lần permute trên
        # tensor lớn (B ở đây là batch*seq_len nên mỗi permute là một bản copy).
        out = self.bn(out.reshape(B * N, -1)).reshape(B, N, -1)
        return self.relu(out)


class HandGCNModel(SignLanguageModel):
    """
    Hierarchical Distance-aware Graph Convolutional Network (HD-GCN) for Hands.
    
    Architecture:
    - Treats hand keypoints as graph nodes.
    - Graph convolution uses distance-aware matrices (D=0, 1, 2) to capture local and semi-local dependencies.
    - Hierarchical Pooling aggregates 21 joints into 6 functional parts (Wrist + 5 Fingers).
    - Temporal convolutions and Attention model the time axis.
    """

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
        **kwargs,
    ):
        super().__init__(input_dim, output_dim, name="HD-GCN")
        self.num_nodes = num_nodes
        self.gcn_channels = gcn_channels
        self.num_gcn_layers = num_gcn_layers
        self.temporal_channels = temporal_channels
        self.dropout_rate = dropout
        self.max_distance = max_distance
        
        # Build multi-distance adjacencies for Fine level (42 nodes)
        fine_adjs = self._build_distance_adjacencies_fine(max_distance)
        for d in range(max_distance + 1):
            self.register_buffer(f"fine_adj_d{d}", fine_adjs[d])
            
        # Build multi-distance adjacencies for Part level (12 nodes: 6 parts x 2 hands)
        part_adjs = self._build_distance_adjacencies_part(max_distance)
        for d in range(max_distance + 1):
            self.register_buffer(f"part_adj_d{d}", part_adjs[d])

        # Define hierarchical mapping matrix (42 -> 12)
        self.register_buffer("hierarchical_pooling_matrix", self._build_pooling_matrix())

        self.input_projection = nn.Linear(input_dim // self.num_nodes, gcn_channels)

        # Fine-level GCNs
        self.fine_gcns = nn.ModuleList([
            DistanceAwareGCNLayer(gcn_channels if i > 0 else gcn_channels, gcn_channels, max_distance)
            for i in range(num_gcn_layers)
        ])
        
        # Part-level GCNs (Hierarchical Layer)
        self.part_gcns = nn.ModuleList([
            DistanceAwareGCNLayer(gcn_channels, gcn_channels, max_distance)
            for _ in range(1)
        ])

        # Temporal processing
        self.temporal_conv1 = nn.Conv1d(gcn_channels, temporal_channels, kernel_size=3, padding=1)
        self.temporal_conv2 = nn.Conv1d(temporal_channels, temporal_channels, kernel_size=3, padding=1)

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

    def _get_shortest_paths(self, num_nodes: int, edges: List[tuple]) -> torch.Tensor:
        # Floyd-Warshall to find shortest paths
        dist = torch.full((num_nodes, num_nodes), float('inf'))
        for i in range(num_nodes):
            dist[i, i] = 0
        for i, j in edges:
            dist[i, j] = 1
            dist[j, i] = 1
            
        for k in range(num_nodes):
            for i in range(num_nodes):
                for j in range(num_nodes):
                    if dist[i, j] > dist[i, k] + dist[k, j]:
                        dist[i, j] = dist[i, k] + dist[k, j]
        return dist

    def _build_distance_adjacencies_fine(self, max_distance: int) -> List[torch.Tensor]:
        edges = [
            (0, 1), (1, 2), (2, 3), (3, 4),          # Thumb
            (0, 5), (5, 6), (6, 7), (7, 8),          # Index
            (0, 9), (9, 10), (10, 11), (11, 12),     # Middle
            (0, 13), (13, 14), (14, 15), (15, 16),   # Ring
            (0, 17), (17, 18), (18, 19), (19, 20),   # Pinky
        ]
        all_edges = []
        for i, j in edges:
            all_edges.append((i, j))
            all_edges.append((i + 21, j + 21))
            
        dist_mat = self._get_shortest_paths(42, all_edges)
        
        adjs = []
        for d in range(max_distance + 1):
            adj = (dist_mat == d).float()
            adjs.append(normalize_adjacency(adj))
            
        return adjs

    def _build_distance_adjacencies_part(self, max_distance: int) -> List[torch.Tensor]:
        # 12 nodes total (6 parts per hand: wrist + 5 fingers)
        edges = [
            (0, 1), (0, 2), (0, 3), (0, 4), (0, 5)
        ]
        all_edges = []
        for i, j in edges:
            all_edges.append((i, j))
            all_edges.append((i + 6, j + 6))
            
        dist_mat = self._get_shortest_paths(12, all_edges)
        
        adjs = []
        for d in range(max_distance + 1):
            adj = (dist_mat == d).float()
            adjs.append(normalize_adjacency(adj))
            
        return adjs

    def _build_pooling_matrix(self) -> torch.Tensor:
        """
        Creates a pooling matrix P [12, 42] mapping joints to parts.
        """
        P = torch.zeros(12, 42)
        
        # Left hand (0-20) -> parts 0-5
        P[0, 0] = 1.0 # wrist
        P[1, 1:5] = 1.0 / 4 # thumb
        P[2, 5:9] = 1.0 / 4 # index
        P[3, 9:13] = 1.0 / 4 # middle
        P[4, 13:17] = 1.0 / 4 # ring
        P[5, 17:21] = 1.0 / 4 # pinky
        
        # Right hand (21-41) -> parts 6-11
        P[6, 21] = 1.0 # wrist
        P[7, 22:26] = 1.0 / 4 # thumb
        P[8, 26:30] = 1.0 / 4 # index
        P[9, 30:34] = 1.0 / 4 # middle
        P[10, 34:38] = 1.0 / 4 # ring
        P[11, 38:42] = 1.0 / 4 # pinky
        
        return P

    def encode(self, x_btd: torch.Tensor) -> torch.Tensor:
        if x_btd.ndim != 3:
            raise RuntimeError(f"Expected 3D tensor [B,T,D], got {x_btd.shape}")

        B, T, D = x_btd.shape
        features_per_node = D // self.num_nodes
        x_graph = x_btd.reshape(B * T, self.num_nodes, features_per_node)

        # 1. Input Projection
        x_graph = self.input_projection(x_graph)
        
        # 2. Fine level Distance-aware GCN
        fine_adjs = [getattr(self, f"fine_adj_d{d}") for d in range(self.max_distance + 1)]
        for gcn_layer in self.fine_gcns:
            x_graph = gcn_layer(x_graph, fine_adjs)
            
        # 3. Hierarchical Pooling (42 nodes -> 12 nodes)
        x_part = torch.matmul(self.hierarchical_pooling_matrix, x_graph)
        
        # 4. Part level Distance-aware GCN
        part_adjs = [getattr(self, f"part_adj_d{d}") for d in range(self.max_distance + 1)]
        for gcn_layer in self.part_gcns:
            x_part = gcn_layer(x_part, part_adjs)

        # 5. Global Node Pooling (Mean over 12 part nodes)
        x_temporal = x_part.mean(dim=1)
        x_temporal = x_temporal.reshape(B, T, self.gcn_channels)

        # 6. Temporal Convolution
        x_temporal = x_temporal.permute(0, 2, 1)
        x_temporal = torch.relu(self.temporal_conv1(x_temporal))
        x_temporal = torch.relu(self.temporal_conv2(x_temporal))
        
        # 7. Attention over Time
        x_attn = x_temporal.permute(0, 2, 1)
        attn_weights = self.attention(x_attn)
        x_pooled = (x_attn * attn_weights).sum(dim=1)

        return x_pooled

    def forward(self, x_btd: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.encode(x_btd))

    @classmethod
    def from_config(
        cls,
        input_dim: int,
        output_dim: int,
        config: Optional[Dict[str, Any]] = None,
    ) -> "HandGCNModel":
        if config is None:
            config = {}

        return cls(
            input_dim=input_dim,
            output_dim=output_dim,
            num_nodes=config.get("num_nodes", 42),
            gcn_channels=config.get("gcn_channels", 64),
            num_gcn_layers=config.get("num_gcn_layers", 2),
            temporal_channels=config.get("temporal_channels", 128),
            dropout=config.get("dropout", 0.3),
            max_distance=config.get("max_distance", 2),
        )

    def get_config(self) -> Dict[str, Any]:
        return {
            "model": "HD-GCN",
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "num_nodes": self.num_nodes,
            "gcn_channels": self.gcn_channels,
            "num_gcn_layers": self.num_gcn_layers,
            "temporal_channels": self.temporal_channels,
            "dropout": self.dropout_rate,
            "max_distance": self.max_distance,
        }
