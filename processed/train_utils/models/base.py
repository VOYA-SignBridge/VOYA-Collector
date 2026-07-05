"""Base class cho tất cả sign language models"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import torch
import torch.nn as nn


def initialize_kaiming(module: nn.Module) -> None:
    """
    Initialize all Conv/Linear/RNN layers with Kaiming Normal (He et al., 2015).

    Kaiming initialization is standard for ReLU networks and ensures:
    - Consistent weight distribution across architectures
    - Proper variance scaling based on network depth
    - Fair comparison between different model types

    Reference: He et al. "Delving Deep into Rectifiers" - ICCV 2015

    Args:
        module: PyTorch module to initialize
    """
    for m in module.modules():
        if isinstance(m, (nn.Conv1d, nn.Conv2d, nn.Linear)):
            nn.init.kaiming_normal_(m.weight, nonlinearity='relu')
            if m.bias is not None:
                nn.init.zeros_(m.bias)
        elif isinstance(m, (nn.LSTM, nn.GRU)):
            # For recurrent layers, initialize weights (not biases)
            for name, param in m.named_parameters():
                if 'weight_ih' in name or 'weight_hh' in name:
                    nn.init.kaiming_normal_(param, nonlinearity='relu')
                elif 'bias' in name:
                    nn.init.zeros_(param)
        elif isinstance(m, nn.BatchNorm1d):
            # BatchNorm: weights to 1, biases to 0
            if m.weight is not None:
                nn.init.ones_(m.weight)
            if m.bias is not None:
                nn.init.zeros_(m.bias)


class SignLanguageModel(ABC, nn.Module):
    """
    Abstract base class cho tất cả sign language models.

    Tất cả models phải implement:
    - forward(x) để inference
    - from_config() để tạo model từ config dict
    - get_model_name() để lấy tên model
    """

    def __init__(
        self,
        input_dim: int,
        output_dim: int,
        name: Optional[str] = None,
        **kwargs,
    ):
        """
        Args:
            input_dim: Số features đầu vào (thường 126 cho sign language)
            output_dim: Số classes đầu ra
            name: Tên model (nếu None dùng class name)
        """
        super().__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim
        self._model_name = name or self.__class__.__name__

    @abstractmethod
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass

        Args:
            x: Input tensor shape (batch, seq_len, input_dim)

        Returns:
            Output logits shape (batch, output_dim)
        """
        pass

    @classmethod
    @abstractmethod
    def from_config(
        cls,
        input_dim: int,
        output_dim: int,
        config: Optional[Dict[str, Any]] = None,
    ):
        """
        Tạo model từ config dict.

        Args:
            input_dim: Input dimension
            output_dim: Output dimension
            config: Dict chứa model-specific hyperparameters
                   (ví dụ: dropout, channels, levels, kernel_size, etc.)

        Returns:
            Model instance
        """
        pass

    def get_model_name(self) -> str:
        """Lấy tên model để log"""
        return self._model_name

    def get_config(self) -> Dict[str, Any]:
        """
        Trả về config của model.
        Override trong subclass nếu cần lưu hyperparameters.
        """
        return {
            "model": self.get_model_name(),
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
        }

    def count_parameters(self) -> int:
        """Đếm tổng số parameters"""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def __repr__(self) -> str:
        """Nice representation"""
        param_count = self.count_parameters()
        return f"{self.get_model_name()}(input_dim={self.input_dim}, output_dim={self.output_dim}, params={param_count:,})"
