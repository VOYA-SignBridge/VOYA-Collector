"""
Sign Language Model Architectures

Supported models:
- TCN: Temporal Convolutional Network
- CNN: Convolutional Neural Network
- LSTM: Long Short-Term Memory
- BiGRU_Attention: Bidirectional GRU with Attention
- HandGCN: Hand Skeleton Graph Convolutional Network
- HandGCN_Lite: HD-GCN with direct in-memory TFLite export support
"""

from .base import SignLanguageModel
from .tcn import TCNModel
from .cnn import CNNModel
from .lstm import LSTMModel
from .bigru_attention import BiGRUAttentionModel
from .hd_gcn import HandGCNModel
from .hd_gcn_lite import HandGCNLiteModel

__all__ = [
    "SignLanguageModel",
    "TCNModel",
    "CNNModel",
    "LSTMModel",
    "BiGRUAttentionModel",
    "HandGCNModel",
    "HandGCNLiteModel",
]

MODEL_REGISTRY = {
    "tcn": TCNModel,
    "cnn": CNNModel,
    "lstm": LSTMModel,
    "bigru_attention": BiGRUAttentionModel,
    "handgcn": HandGCNModel,
    "hdgcn": HandGCNModel,  # Backward compatibility alias
    "hd_gcn": HandGCNModel,
    "hdgcn_lite": HandGCNLiteModel,
}


def get_model(model_name: str, *args, **kwargs):
    """Factory function để lấy model từ registry"""
    if model_name.lower() not in MODEL_REGISTRY:
        available = list(MODEL_REGISTRY.keys())
        raise ValueError(
            f"Unknown model: {model_name}. Available: {available}"
        )
    return MODEL_REGISTRY[model_name.lower()](*args, **kwargs)


def get_model_class(model_name: str):
    """Lấy model class (chưa instantiate)"""
    if model_name.lower() not in MODEL_REGISTRY:
        available = list(MODEL_REGISTRY.keys())
        raise ValueError(
            f"Unknown model: {model_name}. Available: {available}"
        )
    return MODEL_REGISTRY[model_name.lower()]
