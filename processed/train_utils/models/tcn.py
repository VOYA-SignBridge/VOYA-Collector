"""Temporal Convolutional Network (TCN) for sign language recognition"""

import math
from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn

from .base import SignLanguageModel


class Chomp1d(nn.Module):
    """Remove padding after convolution"""

    def __init__(self, chomp_size: int):
        super().__init__()
        self.chomp_size = chomp_size

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x[:, :, : x.size(2) - self.chomp_size]


class TemporalBlock(nn.Module):
    """Single temporal block in TCN"""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        dilation: int,
        dropout: float,
    ) -> None:
        super().__init__()
        pad = (kernel_size - 1) * dilation
        self.conv1 = nn.Conv1d(
            in_channels,
            out_channels,
            kernel_size,
            padding=pad,
            dilation=dilation,
        )
        self.chomp1 = Chomp1d(pad)
        self.relu1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)

        self.conv2 = nn.Conv1d(
            out_channels,
            out_channels,
            kernel_size,
            padding=pad,
            dilation=dilation,
        )
        self.chomp2 = Chomp1d(pad)
        self.relu2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)

        self.downsample = (
            nn.Conv1d(in_channels, out_channels, 1)
            if in_channels != out_channels
            else None
        )
        self.out_relu = nn.ReLU()

        # Kaiming initialization
        for m in [self.conv1, self.conv2]:
            nn.init.kaiming_normal_(m.weight, nonlinearity="relu")
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        if self.downsample is not None:
            nn.init.kaiming_normal_(self.downsample.weight, nonlinearity="linear")
            if self.downsample.bias is not None:
                nn.init.zeros_(self.downsample.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv1(x)
        out = self.chomp1(out)
        out = self.relu1(out)
        out = self.drop1(out)

        out = self.conv2(out)
        out = self.chomp2(out)
        out = self.relu2(out)
        out = self.drop2(out)

        res = x if self.downsample is None else self.downsample(x)
        return self.out_relu(out + res)


class TCNModel(SignLanguageModel):
    """
    Temporal Convolutional Network for sequence classification.

    Architecture:
    - Optional projection layer to normalize input dimension
    - Stack of temporal blocks with exponentially increasing dilation
    - Global average pooling
    - Linear classifier head
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        channels: int = 64,
        levels: int = 3,
        kernel_size: int = 5,
        dropout: float = 0.3,
        use_proj: bool = True,
        proj_dim: Optional[int] = None,
        temporal_pool: str = "gap",
        **kwargs,
    ):
        super().__init__(input_dim, output_dim, name="TCN")
        self.channels = channels
        self.levels = levels
        self.kernel_size = kernel_size
        self.dropout = dropout
        self.use_proj = use_proj
        # Temporal aggregation across the time axis:
        #   "gap"       — global average pooling (legacy default; order-agnostic,
        #                 fine for static/hand-shape signs, WEAK for dynamic
        #                 multi-phase phrases because it averages away temporal order)
        #   "attention" — learned attention over TCN features (each already carries
        #                 local temporal context) → keeps the discriminative phases
        #                 of a phrase like "Tôi đi siêu thị". Best default for new runs.
        #   "mean_max"  — concat(mean, max, last) → cheap order-aware alternative.
        if temporal_pool not in ("gap", "attention", "mean_max"):
            raise ValueError(f"temporal_pool must be gap|attention|mean_max, got {temporal_pool}")
        self.temporal_pool = temporal_pool

        proj_dim = proj_dim or channels
        self.proj = nn.Identity()
        current_in = input_dim

        if use_proj and input_dim != proj_dim:
            self.proj = nn.Conv1d(input_dim, proj_dim, kernel_size=1)
            current_in = proj_dim

        blocks: List[nn.Module] = []
        for i in range(levels):
            dilation = 2 ** i
            blocks.append(
                TemporalBlock(
                    in_channels=current_in if i == 0 else channels,
                    out_channels=channels,
                    kernel_size=kernel_size,
                    dilation=dilation,
                    dropout=dropout,
                )
            )
        self.network = nn.Sequential(*blocks)

        # Pooling head + resulting feature width fed to the classifier.
        if temporal_pool == "attention":
            self.attn = nn.Sequential(
                nn.Linear(channels, channels // 2),
                nn.Tanh(),
                nn.Linear(channels // 2, 1),
            )
            feat_dim = channels
        elif temporal_pool == "mean_max":
            self.attn = None
            feat_dim = channels * 3  # mean ++ max ++ last
        else:
            self.attn = None
            feat_dim = channels

        self.classifier = nn.Linear(feat_dim, output_dim)
        nn.init.kaiming_uniform_(self.classifier.weight, a=math.sqrt(5))
        if self.classifier.bias is not None:
            nn.init.zeros_(self.classifier.bias)
        if self.attn is not None:
            for m in self.attn:
                if isinstance(m, nn.Linear):
                    nn.init.xavier_uniform_(m.weight)
                    if m.bias is not None:
                        nn.init.zeros_(m.bias)

    def encode(self, x_btd: torch.Tensor) -> torch.Tensor:
        """
        Encode sequence to fixed-size representation via global average pooling.

        Args:
            x_btd: Input tensor [B, T, D]
                   B = batch size
                   T = sequence length
                   D = input dimension (126)

        Returns:
            Pooled representation [B, channels]
        """
        if x_btd.ndim != 3:
            raise RuntimeError(f"Expected 3D tensor [B,T,D], got {x_btd.shape}")

        x = x_btd.transpose(1, 2)  # [B, D, T]
        x = self.proj(x)  # [B, proj_dim, T]
        x = self.network(x)  # [B, channels, T]

        if self.temporal_pool == "attention":
            h = x.transpose(1, 2)                    # [B, T, channels]
            w = torch.softmax(self.attn(h), dim=1)   # [B, T, 1] — per-frame weight
            return (h * w).sum(dim=1)                # [B, channels] — order-aware
        if self.temporal_pool == "mean_max":
            mean = x.mean(dim=2)
            mx = x.max(dim=2).values
            last = x[:, :, -1]
            return torch.cat([mean, mx, last], dim=1)  # [B, 3*channels]
        return x.mean(dim=2)  # [B, channels] — global average pooling (legacy)

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
    ) -> "TCNModel":
        """
        Create TCN model from config dict.

        Args:
            input_dim: Input dimension (126)
            output_dim: Number of classes
            config: Dict with keys:
                - channels (int): Number of conv channels. Default: 64
                - levels (int): Number of temporal blocks. Default: 3
                - kernel_size (int): Conv kernel size. Default: 5
                - dropout (float): Dropout rate. Default: 0.3
                - use_proj (bool): Use projection layer. Default: True

        Returns:
            TCNModel instance
        """
        if config is None:
            config = {}

        return cls(
            input_dim=input_dim,
            output_dim=output_dim,
            channels=config.get("channels", 64),
            levels=config.get("levels", 3),
            kernel_size=config.get("kernel_size", 5),
            dropout=config.get("dropout", 0.3),
            use_proj=config.get("use_proj", True),
            # Backward compat: checkpoints trained before this field default to
            # "gap" so existing (e.g. promoted Hòa Đê) models load unchanged.
            temporal_pool=config.get("temporal_pool", "gap"),
        )

    def get_config(self) -> Dict[str, Any]:
        """Get model configuration for logging/saving"""
        return {
            "model": "TCN",
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "channels": self.channels,
            "levels": self.levels,
            "kernel_size": self.kernel_size,
            "dropout": self.dropout,
            "use_proj": self.use_proj,
            "temporal_pool": self.temporal_pool,
        }
