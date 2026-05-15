from __future__ import annotations

import hashlib
import inspect
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn


logger = logging.getLogger("realtime_service.model_loader")


@dataclass(frozen=True)
class ModelBundle:
    model_id: str
    model_name: str

    model: nn.Module
    idx_to_label: List[Dict[str, Any]]

    normalization_version: str
    preprocess_contract: Dict[str, Any]

    checkpoint_sha256: str
    checkpoint_path: str

    language: str
    dialect: Optional[str]

    loaded_at: str
    warmup_ok: bool


def compute_file_sha256(path: str) -> str:
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _torch_load_checkpoint(path: str, map_location: str = "cpu") -> Any:
    """Load a checkpoint dict.

    We *try* `weights_only=True` when supported, but Step 0 checkpoints
    intentionally include metadata (strings/dicts), so we fall back to
    a regular `torch.load` if weights-only cannot represent the content.
    """
    sig = None
    try:
        sig = inspect.signature(torch.load)
    except Exception:
        sig = None

    if sig and "weights_only" in sig.parameters:
        try:
            return torch.load(path, map_location=map_location, weights_only=True)
        except Exception as exc:
            logger.warning("weights_only torch.load failed; falling back to full torch.load: %s", exc)

    return torch.load(path, map_location=map_location)


def load_checkpoint(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"checkpoint not found: {p}")

    obj = _torch_load_checkpoint(str(p), map_location="cpu")
    if not isinstance(obj, dict):
        raise ValueError("checkpoint must be a dict")
    return obj


class TemporalBlock(nn.Module):
    def __init__(self, in_ch: int, out_ch: int, kernel_size: int, stride: int, dilation: int, dropout: float):
        super().__init__()
        padding = (kernel_size - 1) * dilation
        self.conv1 = nn.Conv1d(in_ch, out_ch, kernel_size, stride=stride, padding=padding, dilation=dilation)
        self.relu1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)
        self.conv2 = nn.Conv1d(out_ch, out_ch, kernel_size, stride=stride, padding=padding, dilation=dilation)
        self.relu2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)
        self.downsample = nn.Conv1d(in_ch, out_ch, 1) if in_ch != out_ch else None

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out = self.conv1(x)
        out = self.relu1(out)
        out = self.drop1(out)
        out = self.conv2(out)
        out = self.relu2(out)
        out = self.drop2(out)
        res = x if self.downsample is None else self.downsample(x)
        # Trim for causal padding alignment if needed
        if out.shape[-1] != res.shape[-1]:
            min_t = min(out.shape[-1], res.shape[-1])
            out = out[..., :min_t]
            res = res[..., :min_t]
        return out + res


class TCNClassifier(nn.Module):
    def __init__(self, feature_dim: int, num_classes: int, *, channels: List[int], kernel_size: int = 3, dropout: float = 0.0):
        super().__init__()
        if not channels:
            raise ValueError("TCN channels must be non-empty")
        layers: List[nn.Module] = []
        in_ch = int(feature_dim)
        for i, out_ch in enumerate(channels):
            dilation = 2 ** i
            layers.append(TemporalBlock(in_ch, int(out_ch), int(kernel_size), stride=1, dilation=dilation, dropout=float(dropout)))
            in_ch = int(out_ch)
        self.tcn = nn.Sequential(*layers)
        self.head = nn.Linear(in_ch, int(num_classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # Accept either (B,T,D) or (B,D,T)
        if x.ndim != 3:
            raise ValueError(f"expected 3D tensor, got shape={tuple(x.shape)}")
        if x.shape[1] == 60 and x.shape[2] == 126:
            # (B,T,D) -> (B,D,T)
            x = x.permute(0, 2, 1).contiguous()
        elif x.shape[1] == 126 and x.shape[2] == 60:
            # already (B,D,T)
            pass
        else:
            # Do not reshape; refuse unknown layout
            raise ValueError(f"unexpected input layout for warmup: shape={tuple(x.shape)}")

        y = self.tcn(x)
        # Global average pool over time dim
        y = y.mean(dim=-1)
        return self.head(y)


def build_model_from_checkpoint(ckpt: Dict[str, Any]) -> nn.Module:
    model_type = str(ckpt.get("model_type") or "").strip()
    if model_type != "TCN":
        raise ValueError(f"unsupported model_type for Step 0: {model_type!r}")

    cfg = ckpt.get("model_config")
    if not isinstance(cfg, dict):
        raise ValueError("model_config must be a dict")

    # Minimal, explicit config expectations for this service.
    channels = cfg.get("channels") or cfg.get("num_channels")
    if not isinstance(channels, list) or not channels:
        raise ValueError("model_config must include non-empty list 'channels' (or 'num_channels')")

    kernel_size = int(cfg.get("kernel_size") or 3)
    dropout = float(cfg.get("dropout") or 0.0)

    feature_dim = int(ckpt.get("feature_dim"))
    num_classes = int(ckpt.get("num_classes"))

    return TCNClassifier(feature_dim=feature_dim, num_classes=num_classes, channels=[int(c) for c in channels], kernel_size=kernel_size, dropout=dropout)


def load_weights(model: nn.Module, ckpt: Dict[str, Any]) -> None:
    sd = ckpt.get("model_state_dict")
    if not isinstance(sd, dict):
        raise ValueError("model_state_dict must be a dict")

    incompat = model.load_state_dict(sd, strict=True)
    missing = list(getattr(incompat, "missing_keys", []) or [])
    unexpected = list(getattr(incompat, "unexpected_keys", []) or [])
    if missing or unexpected:
        raise ValueError(f"state_dict mismatch missing={missing} unexpected={unexpected}")


def warmup(model: nn.Module, *, seq_len: int, feature_dim: int, device: str = "cpu") -> None:
    model.eval()
    model.to(device)
    x = torch.zeros((1, int(seq_len), int(feature_dim)), dtype=torch.float32, device=device)
    with torch.no_grad():
        _ = model(x)
    # model stays in eval mode after warmup (never switches back)


def build_bundle(
    *,
    model_id: str,
    model_name: str,
    checkpoint_path: str,
    language: str,
    dialect: Optional[str],
    ckpt: Dict[str, Any],
    checkpoint_sha256: str,
) -> ModelBundle:
    model = build_model_from_checkpoint(ckpt)
    load_weights(model, ckpt)

    # Warmup lifecycle (fail-fast)
    warmup_ok = False
    warmup(model, seq_len=int(ckpt["seq_len"]), feature_dim=int(ckpt["feature_dim"]), device="cpu")
    warmup_ok = True

    loaded_at = datetime.now(timezone.utc).isoformat()

    return ModelBundle(
        model_id=model_id,
        model_name=model_name,
        model=model,
        idx_to_label=ckpt["idx_to_label"],
        normalization_version=str(ckpt["normalization_version"]),
        preprocess_contract=dict(ckpt["preprocess_contract"]),
        checkpoint_sha256=str(checkpoint_sha256),
        checkpoint_path=str(checkpoint_path),
        language=str(language),
        dialect=dialect,
        loaded_at=loaded_at,
        warmup_ok=bool(warmup_ok),
    )
