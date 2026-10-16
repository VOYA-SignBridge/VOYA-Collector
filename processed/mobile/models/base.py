"""Minimal shared base class used by the bundled mobile models."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import torch
import torch.nn as nn


def initialize_kaiming(module: nn.Module) -> None:
    """Initialize layers exactly as in the HD-GCN training repository."""
    for child in module.modules():
        if isinstance(child, (nn.Conv1d, nn.Conv2d, nn.Linear)):
            nn.init.kaiming_normal_(child.weight, nonlinearity="relu")
            if child.bias is not None:
                nn.init.zeros_(child.bias)
        elif isinstance(child, (nn.LSTM, nn.GRU)):
            for name, parameter in child.named_parameters():
                if "weight_ih" in name or "weight_hh" in name:
                    nn.init.kaiming_normal_(parameter, nonlinearity="relu")
                elif "bias" in name:
                    nn.init.zeros_(parameter)
        elif isinstance(child, nn.BatchNorm1d):
            if child.weight is not None:
                nn.init.ones_(child.weight)
            if child.bias is not None:
                nn.init.zeros_(child.bias)


class SignLanguageModel(ABC, nn.Module):
    """Common contract stored in HD-GCN checkpoints."""

    def __init__(self, input_dim: int, output_dim: int, name: Optional[str] = None, **_: Any) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.output_dim = output_dim
        self._model_name = name or self.__class__.__name__

    @abstractmethod
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_config(
        cls,
        input_dim: int,
        output_dim: int,
        config: Optional[Dict[str, Any]] = None,
    ) -> "SignLanguageModel":
        raise NotImplementedError

    def get_model_name(self) -> str:
        return self._model_name

    def get_config(self) -> Dict[str, Any]:
        return {
            "model": self.get_model_name(),
            "input_dim": self.input_dim,
            "output_dim": self.output_dim,
        }

    def count_parameters(self) -> int:
        return sum(parameter.numel() for parameter in self.parameters() if parameter.requires_grad)
