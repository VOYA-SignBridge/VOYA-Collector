"""HD-GCN variant for direct, in-memory LiteRT Torch export.

The graph topology, 42 -> 12 pooling, BatchNorm, temporal convolutions,
attention and classifier come from hd_gcn.py. Only the graph projection's
execution is changed: call each nn.Linear directly instead of concatenating
its parameters inside forward(). This is not a smaller or quantized model.

State-dict keys and tensor shapes match HandGCNModel, including graph buffers.
An ORIGINAL model's in-memory state_dict can therefore be loaded with strict=True.
No LiteRT dependency is imported while constructing or training this model.
"""

from typing import Any, Dict, List

import torch
import torch.nn as nn

from .hd_gcn import DistanceAwareGCNLayer, HandGCNModel


class DistanceAwareGCNLiteLayer(nn.Module):
    """Same sum_d(A_d @ Linear_d(x)) and BatchNorm as the original layer."""

    def __init__(self, source: DistanceAwareGCNLayer):
        super().__init__()
        # Reuse the original initialized modules without adding a nesting level
        # to state_dict keys or changing the initialization/RNG sequence.
        self.max_distance = source.max_distance
        self.out_channels = source.out_channels
        self.linear_layers = source.linear_layers
        self.bn = source.bn
        self.relu = nn.ReLU(inplace=False)

    def forward(self, x: torch.Tensor, adjs: List[torch.Tensor]) -> torch.Tensor:
        batch, nodes, _ = x.shape
        out = torch.matmul(adjs[0], self.linear_layers[0](x))
        for distance in range(1, self.max_distance + 1):
            out = out + torch.matmul(adjs[distance], self.linear_layers[distance](x))
        out = self.bn(out.reshape(batch * nodes, self.out_channels))
        return self.relu(out.reshape(batch, nodes, self.out_channels))


class HandGCNLiteModel(HandGCNModel):
    """Trainable HD-GCN using the original graph and configuration interface.

    Input: float tensor [batch, frames, input_dim], already preprocessed in the
    SAME way as the training data. The usual contract is [batch, 60, 126].
    Output: raw class logits [batch, output_dim], without softmax.

    Export is a separate post-training operation; constructing this class does
    not create a .pt or .tflite file. See train_utils/export_tflite.py.
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
        **kwargs: Any,
    ):
        # The inherited adjacency and pooling builders describe exactly 42
        # nodes. Fail early rather than silently interpreting another layout.
        if num_nodes != 42:
            raise ValueError("HandGCNLiteModel requires 42 hand nodes")
        if input_dim <= 0 or input_dim % num_nodes:
            raise ValueError("input_dim must be a positive multiple of 42")
        if output_dim <= 0 or gcn_channels <= 0 or temporal_channels < 2:
            raise ValueError("Invalid class count or channel widths")
        if num_gcn_layers < 1 or max_distance < 0:
            raise ValueError("num_gcn_layers must be >= 1 and max_distance >= 0")

        super().__init__(
            input_dim=input_dim,
            output_dim=output_dim,
            num_nodes=num_nodes,
            gcn_channels=gcn_channels,
            num_gcn_layers=num_gcn_layers,
            temporal_channels=temporal_channels,
            dropout=dropout,
            max_distance=max_distance,
            **kwargs,
        )
        self._model_name = "HandGCN_Lite"
        self.fine_gcns = nn.ModuleList(
            DistanceAwareGCNLiteLayer(layer) for layer in self.fine_gcns
        )
        self.part_gcns = nn.ModuleList(
            DistanceAwareGCNLiteLayer(layer) for layer in self.part_gcns
        )
        # Out-of-place activations simplify graph capture without changing the
        # mathematical network. The original HandGCN class remains untouched.
        for module in self.modules():
            if isinstance(module, nn.ReLU):
                module.inplace = False

    # HandGCNModel.from_config() constructs cls(...), so it also rebuilds this
    # subclass and preserves every original architecture hyperparameter.
    def get_config(self) -> Dict[str, Any]:
        return {**super().get_config(), "model": self.get_model_name()}
