"""Hand Dynamics Graph Convolutional Network for sign language recognition"""

from typing import Any, Dict, Optional

import torch
import torch.nn as nn

from .base import SignLanguageModel, initialize_kaiming


class GraphConvLayer(nn.Module):
    """
    Graph Convolutional Layer (Kipf & Welling, ICLR 2017).

    Implements: h' = σ(A_norm @ h @ W + b)
    where A_norm = D^(-1/2) * A * D^(-1/2) is row-normalized adjacency
    """

    def __init__(self, in_channels: int, out_channels: int):
        super().__init__()
        self.linear = nn.Linear(in_channels, out_channels)
        self.bn = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)

        # Kaiming initialization for linear layer
        nn.init.kaiming_normal_(self.linear.weight, nonlinearity='relu')
        if self.linear.bias is not None:
            nn.init.zeros_(self.linear.bias)

    def forward(self, x: torch.Tensor, adj: torch.Tensor) -> torch.Tensor:
        """
        Graph convolution: h' = σ(A_norm @ h @ W)

        Args:
            x: [B, N, in_channels] node features
            adj: [N, N] normalized adjacency matrix (pre-normalized)

        Returns:
            [B, N, out_channels] output features
        """
        B, N, C = x.shape

        # Linear transformation: [B, N, C] → [B, N, out_channels]
        x_linear = self.linear(x)  # [B, N, out_channels]

        # Graph aggregation: A_norm @ x @ W (neighbor aggregation)
        # adj: [N, N], x_linear: [B, N, out_channels]
        adj_expanded = adj.unsqueeze(0).expand(B, -1, -1).to(x.device)  # [B, N, N]
        x_agg = torch.bmm(adj_expanded, x_linear)  # [B, N, out_channels]

        # Batch normalization (across channel dimension for each node)
        x_agg = x_agg.permute(0, 2, 1)  # [B, out_channels, N]
        x_agg = self.bn(x_agg)
        x_agg = x_agg.permute(0, 2, 1)  # [B, N, out_channels]

        return self.relu(x_agg)


class HandGCNModel(SignLanguageModel):
    """
    Hand Skeleton Graph Convolutional Network (Kipf & Welling, ICLR 2017).

    Architecture:
    - Treats hand keypoints as graph nodes (21 points per hand × 2 hands = 42 total)
    - Uses graph convolutional layers to capture hand skeleton dynamics
    - Temporal convolutions for sequence modeling over time
    - Attention mechanism to emphasize important frames

    Graph Construction:
    - Nodes (42): 21 left-hand keypoints (0-20) + 21 right-hand keypoints (21-41)
    - Edges: Anatomical skeleton connections within each hand
      * Thumb, Index, Middle, Ring, Pinky chains
      * Self-loops for identity preservation
    - Features: [x, y, z] coordinates per node (3 features/node)
    - Normalization: D^(-1/2) * A * D^(-1/2) (symmetric normalization)

    Input/Output:
    - Input: [B, T, 126] → 2 hands × 21 keypoints × 3 coordinates
    - Process: GCN layers → Temporal convolutions → Attention pooling
    - Output: [B, output_dim] class logits

    Strengths:
    - Captures anatomical hand structure explicitly
    - Separate processing of left/right hands
    - Graph convolution respects hand skeleton topology
    - Efficient for skeleton-based representation

    Limitations:
    - Assumes fixed hand topology (may not generalize to occluded hands)
    - Requires accurate hand landmark detection
    - More parameters than CNN baseline
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        num_nodes: int = 42,  # 2 hands × 21 keypoints (DUAL-HAND)
        gcn_channels: int = 64,
        num_gcn_layers: int = 2,
        temporal_channels: int = 128,
        dropout: float = 0.3,
        **kwargs,
    ):
        """
        Args:
            input_dim: Input dimension (typically 126 for 2 hands × 21 points × 3 coords)
            output_dim: Number of output classes
            num_nodes: Number of hand keypoints (42 for dual-hand: 21 left + 21 right)
            gcn_channels: Channels for GCN layers
            num_gcn_layers: Number of graph conv layers
            temporal_channels: Channels for temporal processing
            dropout: Dropout rate

        Architecture:
            - Graph: 42 nodes representing 2 hands (MediaPipe format)
              * Nodes 0-20: Left hand (21 keypoints)
              * Nodes 21-41: Right hand (21 keypoints)
            - Edges: Anatomical skeleton within each hand + optional cross-hand coordination
            - Normalization: Symmetric normalization D^(-1/2) * A * D^(-1/2)
        """
        super().__init__(input_dim, output_dim, name="HandGCN")
        self.num_nodes = num_nodes
        self.gcn_channels = gcn_channels
        self.num_gcn_layers = num_gcn_layers
        self.temporal_channels = temporal_channels
        self.dropout_rate = dropout

        # Dual-hand keypoint adjacency matrix (hand skeleton connections)
        # Nodes 0-20: Left hand, Nodes 21-41: Right hand
        self.register_buffer("hand_adjacency", self._build_hand_adjacency())

        # Initial feature projection
        # Input: [B, T, input_dim] → [B, T, num_nodes, features_per_node]
        self.input_projection = nn.Linear(input_dim // self.num_nodes, gcn_channels)

        # Graph Convolutional Layers
        self.gcn_layers = nn.ModuleList([
            GraphConvLayer(gcn_channels if i > 0 else gcn_channels, gcn_channels)
            for i in range(num_gcn_layers)
        ])

        # Temporal processing (1D convolutions)
        self.temporal_conv1 = nn.Conv1d(gcn_channels, temporal_channels, kernel_size=3, padding=1)
        self.temporal_conv2 = nn.Conv1d(temporal_channels, temporal_channels, kernel_size=3, padding=1)

        # Attention over time
        self.attention = nn.Sequential(
            nn.Linear(temporal_channels, temporal_channels // 2),
            nn.ReLU(inplace=True),
            nn.Linear(temporal_channels // 2, 1),
            nn.Softmax(dim=1),
        )

        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(temporal_channels, temporal_channels // 2),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(temporal_channels // 2, output_dim),
        )

        # Initialize weights with Kaiming Normal (He et al., 2015)
        initialize_kaiming(self)

    def _build_hand_adjacency(self) -> torch.Tensor:
        """
        Build dual-hand skeleton adjacency matrix with symmetric normalization.

        Structure (42 nodes):
          - Nodes 0-20: Left hand (21 keypoints from MediaPipe)
          - Nodes 21-41: Right hand (21 keypoints from MediaPipe)

        Edges: Anatomical connections within each hand
          - Thumb: 0→1→2→3→4 (and 21→22→23→24→25)
          - Index: 0→5→6→7→8 (and 21→26→27→28→29)
          - Middle: 0→9→10→11→12 (and 21→30→31→32→33)
          - Ring: 0→13→14→15→16 (and 21→34→35→36→37)
          - Pinky: 0→17→18→19→20 (and 21→38→39→40→41)

        Reference: MediaPipe Hands pose model (21 keypoints per hand)
        """
        adj = torch.zeros(self.num_nodes, self.num_nodes)

        # Single hand skeleton template
        hand_skeleton_edges = [
            # Thumb (0-4)
            (0, 1), (1, 2), (2, 3), (3, 4),
            # Index (0, 5-8)
            (0, 5), (5, 6), (6, 7), (7, 8),
            # Middle (0, 9-12)
            (0, 9), (9, 10), (10, 11), (11, 12),
            # Ring (0, 13-16)
            (0, 13), (13, 14), (14, 15), (15, 16),
            # Pinky (0, 17-20)
            (0, 17), (17, 18), (18, 19), (19, 20),
        ]

        # Add left hand edges (nodes 0-20)
        for i, j in hand_skeleton_edges:
            adj[i, j] = 1
            adj[j, i] = 1

        # Add right hand edges (nodes 21-41)
        # Offset by 21 to get right hand node indices
        for i, j in hand_skeleton_edges:
            adj[i + 21, j + 21] = 1
            adj[j + 21, i + 21] = 1

        # Add self-loops (identity connection)
        adj = adj + torch.eye(self.num_nodes)

        # Symmetric normalization: D^(-1/2) * A * D^(-1/2)
        # This is the normalized adjacency from Kipf & Welling (2017)
        degree = adj.sum(dim=1)  # [num_nodes]
        degree_inv_sqrt = torch.pow(degree + 1e-6, -0.5)  # Avoid division by zero
        degree_inv_sqrt[torch.isinf(degree_inv_sqrt)] = 0.0

        # D^(-1/2) @ A @ D^(-1/2)
        degree_mat_inv_sqrt = torch.diag(degree_inv_sqrt)
        adj_normalized = degree_mat_inv_sqrt @ adj @ degree_mat_inv_sqrt

        return adj_normalized

    def encode(self, x_btd: torch.Tensor) -> torch.Tensor:
        """
        Encode sequence to fixed-size representation using graph convolution.

        Args:
            x_btd: Input tensor [B, T, D]
                   B = batch size
                   T = sequence length
                   D = input dimension (126)

        Returns:
            Pooled representation [B, temporal_channels]
        """
        if x_btd.ndim != 3:
            raise RuntimeError(f"Expected 3D tensor [B,T,D], got {x_btd.shape}")

        B, T, D = x_btd.shape

        # Reshape to [B*T, num_nodes, features_per_node]
        features_per_node = D // self.num_nodes
        x_graph = x_btd.reshape(B * T, self.num_nodes, features_per_node)

        # Project to GCN channels
        x_graph = self.input_projection(x_graph)  # [B*T, num_nodes, gcn_channels]

        # Apply GCN layers
        adj = self.hand_adjacency.to(x_graph.device)
        for gcn_layer in self.gcn_layers:
            x_graph = gcn_layer(x_graph, adj)

        # Global node pooling (mean over nodes)
        x_temporal = x_graph.mean(dim=1)  # [B*T, gcn_channels]

        # Reshape back to [B, T, gcn_channels]
        x_temporal = x_temporal.reshape(B, T, self.gcn_channels)

        # Temporal processing: [B, T, gcn_channels] → [B, temporal_channels, T]
        x_temporal = x_temporal.permute(0, 2, 1)
        x_temporal = torch.relu(self.temporal_conv1(x_temporal))
        x_temporal = torch.relu(self.temporal_conv2(x_temporal))  # [B, temporal_channels, T]

        # Attention over time
        x_attn = x_temporal.permute(0, 2, 1)  # [B, T, temporal_channels]
        attn_weights = self.attention(x_attn)  # [B, T, 1]
        x_pooled = (x_attn * attn_weights).sum(dim=1)  # [B, temporal_channels]

        return x_pooled

    def forward(self, x_btd: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            x_btd: Input tensor [B, T, D]

        Returns:
            Class logits [B, output_dim]
        """
        return self.classifier(self.encode(x_btd))

    @classmethod
    def from_config(
        cls,
        input_dim: int,
        output_dim: int,
        config: Optional[Dict[str, Any]] = None,
    ) -> "HDGCNModel":
        """
        Create HDGCN model from config dict.

        Args:
            input_dim: Input dimension (126)
            output_dim: Number of classes
            config: Dict with keys:
                - num_nodes (int): Number of hand keypoints (42 for dual-hand). Default: 42
                - gcn_channels (int): GCN hidden channels. Default: 64
                - num_gcn_layers (int): Number of GCN layers. Default: 2
                - temporal_channels (int): Temporal conv channels. Default: 128
                - dropout (float): Dropout rate. Default: 0.3

        Returns:
            HDGCNModel instance
        """
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
        )

    def get_config(self) -> Dict[str, Any]:
        """Get model configuration for logging/saving"""
        return {
            "model": "HandGCN",
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "num_nodes": self.num_nodes,
            "gcn_channels": self.gcn_channels,
            "num_gcn_layers": self.num_gcn_layers,
            "temporal_channels": self.temporal_channels,
            "dropout": self.dropout_rate,
        }
