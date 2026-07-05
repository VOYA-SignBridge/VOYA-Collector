"""Convolutional Neural Network (CNN) for sign language recognition"""

from typing import Any, Dict, List, Optional

import torch
import torch.nn as nn

from .base import SignLanguageModel, initialize_kaiming


class CNNModel(SignLanguageModel):
    """
    Simple CNN architecture for sequence classification.

    Architecture:
    - Conv1d layers with batch norm and ReLU activations
    - Max pooling for dimensionality reduction
    - Global average pooling for fixed-size output
    - Linear classifier head

    This is a baseline model to compare against TCN and other architectures.
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        channels: int = 64,
        kernel_size: int = 5,
        dropout: float = 0.3,
        num_conv_layers: int = 3,
        **kwargs,
    ):
        """
        Args:
            input_dim: Input dimension (typically 126 for sign language)
            output_dim: Number of output classes
            channels: Base number of filters in conv layers
            kernel_size: Convolution kernel size
            dropout: Dropout rate
            num_conv_layers: Number of convolutional layers (1-4)
        """
        super().__init__(input_dim, output_dim, name="CNN")
        self.channels = channels
        self.kernel_size = kernel_size
        self.dropout = dropout
        self.num_conv_layers = max(1, min(4, num_conv_layers))

        # Build convolutional layers
        conv_layers: List[nn.Module] = []
        in_channels = input_dim
        out_channels = channels

        for i in range(self.num_conv_layers):
            # Conv1d block: Conv -> BatchNorm -> ReLU -> Dropout
            conv_layers.append(
                nn.Conv1d(
                    in_channels,
                    out_channels,
                    kernel_size=kernel_size,
                    padding=kernel_size // 2,
                )
            )
            conv_layers.append(nn.BatchNorm1d(out_channels))
            conv_layers.append(nn.ReLU(inplace=True))
            conv_layers.append(nn.Dropout(dropout))

            # Max pool every other layer to reduce temporal dimension
            if i < self.num_conv_layers - 1:
                conv_layers.append(nn.MaxPool1d(kernel_size=2, stride=2))

            in_channels = out_channels
            # Gradually increase channels
            out_channels = channels * (2 ** (i + 1))

        self.conv_block = nn.Sequential(*conv_layers)

        # Classifier head
        self.classifier = nn.Sequential(
            nn.Linear(in_channels, in_channels // 2),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(in_channels // 2, output_dim),
        )

        # Initialize weights with Kaiming Normal (He et al., 2015)
        initialize_kaiming(self)

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
        x = self.conv_block(x)  # [B, out_channels, T']
        return x.mean(dim=2)  # [B, out_channels] — global average pooling

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
    ) -> "CNNModel":
        """
        Create CNN model from config dict.

        Args:
            input_dim: Input dimension (126)
            output_dim: Number of classes
            config: Dict with keys:
                - channels (int): Base number of conv filters. Default: 64
                - kernel_size (int): Conv kernel size. Default: 5
                - dropout (float): Dropout rate. Default: 0.3
                - num_conv_layers (int): Number of conv layers (1-4). Default: 3

        Returns:
            CNNModel instance
        """
        if config is None:
            config = {}

        return cls(
            input_dim=input_dim,
            output_dim=output_dim,
            channels=config.get("channels", 64),
            kernel_size=config.get("kernel_size", 5),
            dropout=config.get("dropout", 0.3),
            num_conv_layers=config.get("num_conv_layers", 3),
        )

    def get_config(self) -> Dict[str, Any]:
        """Get model configuration for logging/saving"""
        return {
            "model": "CNN",
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "channels": self.channels,
            "kernel_size": self.kernel_size,
            "dropout": self.dropout,
            "num_conv_layers": self.num_conv_layers,
        }
