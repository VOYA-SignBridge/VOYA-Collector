"""Long Short-Term Memory (LSTM) for sign language recognition"""

from typing import Any, Dict, Optional

import torch
import torch.nn as nn

from .base import SignLanguageModel, initialize_kaiming


class LSTMModel(SignLanguageModel):
    """
    LSTM (Long Short-Term Memory) architecture for sequence classification.

    Architecture:
    - Bidirectional LSTM layers for processing sequential data
    - Dropout for regularization
    - Global average pooling over sequence dimension
    - Linear classifier head

    LSTMs are well-suited for capturing long-range dependencies in sequences,
    making them particularly effective for sign language recognition where
    temporal patterns are crucial.
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3,
        bidirectional: bool = True,
        **kwargs,
    ):
        """
        Args:
            input_dim: Input dimension (typically 126 for sign language)
            output_dim: Number of output classes
            hidden_size: Number of LSTM hidden units
            num_layers: Number of LSTM layers (1-4)
            dropout: Dropout rate between layers
            bidirectional: Use bidirectional LSTM (default: True)
        """
        super().__init__(input_dim, output_dim, name="LSTM")
        self.hidden_size = hidden_size
        self.num_layers = max(1, min(4, num_layers))
        self.dropout_rate = dropout
        self.bidirectional = bidirectional

        # LSTM layers
        # Input: [B, T, D] -> [B, T, hidden_size * (2 if bidirectional)]
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_size,
            num_layers=self.num_layers,
            dropout=dropout if self.num_layers > 1 else 0.0,
            bidirectional=bidirectional,
            batch_first=True,
        )

        # Output projection
        lstm_output_dim = hidden_size * (2 if bidirectional else 1)

        # Classifier head
        self.classifier = nn.Sequential(
            nn.Linear(lstm_output_dim, lstm_output_dim // 2),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(lstm_output_dim // 2, output_dim),
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
            Pooled representation [B, hidden_size * (2 if bidirectional)]
        """
        if x_btd.ndim != 3:
            raise RuntimeError(f"Expected 3D tensor [B,T,D], got {x_btd.shape}")

        # LSTM forward pass
        # lstm_out: [B, T, hidden_size * (2 if bidirectional)]
        # (h_n, c_n) are the final hidden and cell states
        lstm_out, (h_n, c_n) = self.lstm(x_btd)

        # Global average pooling over time dimension
        # [B, T, hidden_size * 2] -> [B, hidden_size * 2]
        return lstm_out.mean(dim=1)

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
    ) -> "LSTMModel":
        """
        Create LSTM model from config dict.

        Args:
            input_dim: Input dimension (126)
            output_dim: Number of classes
            config: Dict with keys:
                - hidden_size (int): LSTM hidden units. Default: 64
                - num_layers (int): Number of LSTM layers (1-4). Default: 2
                - dropout (float): Dropout rate. Default: 0.3
                - bidirectional (bool): Use bidirectional LSTM. Default: True

        Returns:
            LSTMModel instance
        """
        if config is None:
            config = {}

        return cls(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_size=config.get("hidden_size", 64),
            num_layers=config.get("num_layers", 2),
            dropout=config.get("dropout", 0.3),
            bidirectional=config.get("bidirectional", True),
        )

    def get_config(self) -> Dict[str, Any]:
        """Get model configuration for logging/saving"""
        return {
            "model": "LSTM",
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "dropout": self.dropout_rate,
            "bidirectional": self.bidirectional,
        }
