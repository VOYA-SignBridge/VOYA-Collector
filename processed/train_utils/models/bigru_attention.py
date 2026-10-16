"""Bidirectional GRU with Attention for sign language recognition"""

from typing import Any, Dict, Optional

import torch
import torch.nn as nn

from .base import SignLanguageModel, initialize_kaiming


class AttentionLayer(nn.Module):
    """
    Scaled Dot-Product Attention Mechanism (Vaswani et al., 2017).

    Computes: Attention(Q, K, V) = softmax(Q @ K^T / sqrt(d_k)) @ V
    where d_k is the dimension of keys (hidden_size).

    Reference: "Attention Is All You Need" - NIPS 2017
    """

    def __init__(self, hidden_size: int):
        super().__init__()
        self.query = nn.Linear(hidden_size, hidden_size)
        self.key = nn.Linear(hidden_size, hidden_size)
        self.value = nn.Linear(hidden_size, hidden_size)
        self.scale = hidden_size ** 0.5

        # Kaiming initialization for attention projections
        for module in [self.query, self.key, self.value]:
            nn.init.kaiming_normal_(module.weight, nonlinearity='relu')
            if module.bias is not None:
                nn.init.zeros_(module.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Compute scaled dot-product attention.

        Args:
            x: [B, T, hidden_size] input sequence

        Returns:
            [B, T, hidden_size] attention-weighted output
        """
        Q = self.query(x)  # [B, T, hidden_size]
        K = self.key(x)    # [B, T, hidden_size]
        V = self.value(x)  # [B, T, hidden_size]

        # Scaled dot-product attention: softmax(Q @ K^T / sqrt(d_k)) @ V
        scores = torch.matmul(Q, K.transpose(-2, -1)) / self.scale  # [B, T, T]
        attn_weights = torch.softmax(scores, dim=-1)                # [B, T, T]
        context = torch.matmul(attn_weights, V)                     # [B, T, hidden_size]

        return context


class BiGRUAttentionModel(SignLanguageModel):
    """
    Bidirectional GRU with Scaled Dot-Product Attention (Vaswani et al., 2017).

    Architecture:
    - Bidirectional GRU layers for bidirectional sequence processing
    - Scaled dot-product attention mechanism for temporal focus
    - Global average pooling over time for fixed-size representation
    - Linear classifier head

    Why this architecture for sign language:
    - BiGRU processes both past and future context (crucial for gesture understanding)
    - Attention weights temporal importance (some frames matter more for classification)
    - Combined: captures long-range dependencies + temporal focus
    - Fewer parameters than multi-head attention, good for small datasets

    Computational complexity:
    - BiGRU: O(T * hidden_size^2) for T time steps
    - Attention: O(T^2 * hidden_size) for T^2 attention matrix
    - Total: Efficient for sequence lengths T < 100 (typical for sign language)
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        hidden_size: int = 64,
        num_layers: int = 2,
        dropout: float = 0.3,
        **kwargs,
    ):
        """
        Args:
            input_dim: Input dimension (typically 126 for sign language)
            output_dim: Number of output classes
            hidden_size: GRU hidden units
            num_layers: Number of GRU layers (1-4)
            dropout: Dropout rate between GRU layers
        """
        super().__init__(input_dim, output_dim, name="BiGRU + Attention")
        self.hidden_size = hidden_size
        self.num_layers = max(1, min(4, num_layers))
        self.dropout_rate = dropout

        # Bidirectional GRU layers
        # Output: [B, T, hidden_size * 2]
        self.gru = nn.GRU(
            input_size=input_dim,
            hidden_size=hidden_size,
            num_layers=self.num_layers,
            dropout=dropout if self.num_layers > 1 else 0.0,
            bidirectional=True,
            batch_first=True,
        )

        # Attention mechanism
        gru_output_dim = hidden_size * 2  # bidirectional
        self.attention = AttentionLayer(gru_output_dim)

        # Classifier head
        self.classifier = nn.Sequential(
            nn.Linear(gru_output_dim, gru_output_dim // 2),
            nn.ReLU(inplace=True),
            nn.Dropout(dropout),
            nn.Linear(gru_output_dim // 2, output_dim),
        )

        # Initialize weights with Kaiming Normal (He et al., 2015)
        initialize_kaiming(self)

    def encode(self, x_btd: torch.Tensor) -> torch.Tensor:
        """
        Encode sequence to fixed-size representation with attention.

        Args:
            x_btd: Input tensor [B, T, D]
                   B = batch size
                   T = sequence length
                   D = input dimension (126)

        Returns:
            Pooled representation [B, gru_output_dim]
        """
        if x_btd.ndim != 3:
            raise RuntimeError(f"Expected 3D tensor [B,T,D], got {x_btd.shape}")

        # GRU forward pass
        # gru_out: [B, T, hidden_size * 2]
        gru_out, _ = self.gru(x_btd)

        # Apply attention
        # attn_out: [B, T, hidden_size * 2]
        attn_out = self.attention(gru_out)

        # Global average pooling over time dimension
        # [B, T, hidden_size * 2] -> [B, hidden_size * 2]
        return attn_out.mean(dim=1)

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
    ) -> "BiGRUAttentionModel":
        """
        Create BiGRU+Attention model from config dict.

        Args:
            input_dim: Input dimension (126)
            output_dim: Number of classes
            config: Dict with keys:
                - hidden_size (int): GRU hidden units. Default: 64
                - num_layers (int): Number of GRU layers (1-4). Default: 2
                - dropout (float): Dropout rate. Default: 0.3

        Returns:
            BiGRUAttentionModel instance
        """
        if config is None:
            config = {}

        return cls(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_size=config.get("hidden_size", 64),
            num_layers=config.get("num_layers", 2),
            dropout=config.get("dropout", 0.3),
        )

    def get_config(self) -> Dict[str, Any]:
        """Get model configuration for logging/saving"""
        return {
            "model": "BiGRU + Attention",
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "dropout": self.dropout_rate,
        }
