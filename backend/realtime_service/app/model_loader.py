from __future__ import annotations

import hashlib
import inspect
import math
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import torch
import torch.nn as nn

from .contracts import validate_labels


logger = logging.getLogger("realtime_service.model_loader")


def resolve_device() -> str:
    """Pick inference device from REALTIME_DEVICE env.

    Default 'cpu' — deliberately safe when a training job holds the GPU
    (VRAM contention would otherwise stall/crash both). Set REALTIME_DEVICE=cuda
    to move realtime inference onto the GPU when it is free.
    Falls back to CPU if cuda is requested but unavailable.
    """
    want = (os.getenv("REALTIME_DEVICE", "cpu") or "cpu").strip().lower()
    if want in ("cuda", "gpu"):
        try:
            if torch.cuda.is_available():
                return "cuda"
            logger.warning("[DEVICE] REALTIME_DEVICE=%s but CUDA unavailable — using cpu", want)
        except Exception:
            logger.warning("[DEVICE] CUDA probe failed — using cpu")
    return "cpu"


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

        # torch >= 2.6 defaults weights_only=True, so the fallback must opt out
        # explicitly — otherwise it repeats the failure above.
        return torch.load(path, map_location=map_location, weights_only=False)

    return torch.load(path, map_location=map_location)


def load_checkpoint(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"checkpoint not found: {p}")

    obj = _torch_load_checkpoint(str(p), map_location="cpu")
    if not isinstance(obj, dict):
        raise ValueError("checkpoint must be a dict")
    return obj


class Chomp1d(nn.Module):
    def __init__(self, chomp_size: int):
        super().__init__()
        self.chomp_size = int(chomp_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if self.chomp_size <= 0:
            return x
        return x[:, :, : x.size(2) - self.chomp_size]


class TemporalBlock(nn.Module):
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
        self.conv1 = nn.Conv1d(in_channels, out_channels, kernel_size, padding=pad, dilation=dilation)
        self.chomp1 = Chomp1d(pad)
        self.relu1 = nn.ReLU()
        self.drop1 = nn.Dropout(dropout)

        self.conv2 = nn.Conv1d(out_channels, out_channels, kernel_size, padding=pad, dilation=dilation)
        self.chomp2 = Chomp1d(pad)
        self.relu2 = nn.ReLU()
        self.drop2 = nn.Dropout(dropout)

        self.downsample = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else None
        self.out_relu = nn.ReLU()

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


class TCNClassifier(nn.Module):
    def __init__(
        self,
        in_dim: int,
        num_classes: int,
        channels: int = 64,
        levels: int = 3,
        kernel_size: int = 5,
        dropout: float = 0.3,
        use_proj: bool = True,
        proj_dim: Optional[int] = None,
        temporal_pool: str = "gap",
    ) -> None:
        super().__init__()
        # MUST mirror processed/train_utils/models/tcn.py exactly (same submodule
        # names + feature widths) so a trained state_dict loads with strict=True.
        if temporal_pool not in ("gap", "attention", "mean_max"):
            raise ValueError(f"temporal_pool must be gap|attention|mean_max, got {temporal_pool}")
        self.temporal_pool = temporal_pool
        proj_dim = int(proj_dim or channels)
        self.proj: nn.Module = nn.Identity()
        current_in = int(in_dim)
        if use_proj and int(in_dim) != proj_dim:
            self.proj = nn.Conv1d(int(in_dim), proj_dim, kernel_size=1)
            current_in = proj_dim

        blocks: List[nn.Module] = []
        for i in range(int(levels)):
            dilation = 2 ** i
            blocks.append(
                TemporalBlock(
                    in_channels=current_in if i == 0 else int(channels),
                    out_channels=int(channels),
                    kernel_size=int(kernel_size),
                    dilation=dilation,
                    dropout=float(dropout),
                )
            )
        self.network = nn.Sequential(*blocks)

        if temporal_pool == "attention":
            self.attn: Optional[nn.Module] = nn.Sequential(
                nn.Linear(int(channels), int(channels) // 2),
                nn.Tanh(),
                nn.Linear(int(channels) // 2, 1),
            )
            feat_dim = int(channels)
        elif temporal_pool == "mean_max":
            self.attn = None
            feat_dim = int(channels) * 3
        else:
            self.attn = None
            feat_dim = int(channels)

        self.classifier = nn.Linear(feat_dim, int(num_classes))
        nn.init.kaiming_uniform_(self.classifier.weight, a=math.sqrt(5))
        if self.classifier.bias is not None:
            nn.init.zeros_(self.classifier.bias)

    def forward(self, x_btd: torch.Tensor) -> torch.Tensor:
        if x_btd.ndim != 3:
            raise RuntimeError(f"Expected 3D tensor [B,T,D], got {x_btd.shape}")

        if x_btd.shape[-1] != 126:
            raise RuntimeError(f"Expected feature_dim=126, got {x_btd.shape}")

        x = x_btd.transpose(1, 2)
        x = self.proj(x)
        x = self.network(x)

        if self.temporal_pool == "attention" and self.attn is not None:
            h = x.transpose(1, 2)                    # [B, T, channels]
            w = torch.softmax(self.attn(h), dim=1)   # [B, T, 1]
            pooled = (h * w).sum(dim=1)
        elif self.temporal_pool == "mean_max":
            pooled = torch.cat([x.mean(dim=2), x.max(dim=2).values, x[:, :, -1]], dim=1)
        else:
            pooled = x.mean(dim=2)
        logits = self.classifier(pooled)
        return logits


def build_model_from_checkpoint(ckpt: Dict[str, Any]) -> nn.Module:
    model_type = str(ckpt.get("model_type") or "").strip()
    if model_type != "TCN":
        raise ValueError(f"unsupported model_type for Step 0: {model_type!r}")

    cfg = ckpt.get("model_config")
    if not isinstance(cfg, dict):
        raise ValueError("model_config must be a dict")

    channels_value = cfg.get("channels") or cfg.get("num_channels")
    if isinstance(channels_value, list):
        if not channels_value:
            raise ValueError("model_config must include non-empty 'channels' or 'num_channels'")
        channels = int(channels_value[0])
    elif channels_value is not None:
        channels = int(channels_value)
    else:
        raise ValueError("model_config must include 'channels' (int or list) or 'num_channels'")

    levels = int(cfg.get("levels") or 3)
    kernel_size = int(cfg.get("kernel_size") or 5)
    dropout = float(cfg.get("dropout") or 0.3)
    proj_dim = int(cfg.get("proj_dim") or channels)

    feature_dim = int(ckpt.get("feature_dim"))
    num_classes = int(ckpt.get("num_classes"))

    return TCNClassifier(
        in_dim=feature_dim,
        num_classes=num_classes,
        channels=channels,
        levels=levels,
        kernel_size=kernel_size,
        dropout=dropout,
        use_proj=bool(cfg.get("use_proj", True)),
        proj_dim=proj_dim,
        # Old checkpoints have no temporal_pool -> "gap" (unchanged behaviour).
        temporal_pool=str(cfg.get("temporal_pool", "gap")),
    )


def load_weights(model: nn.Module, ckpt: Dict[str, Any]) -> None:
    sd = ckpt.get("model_state_dict")
    if not isinstance(sd, dict):
        raise ValueError("model_state_dict must be a dict")

    incompat = model.load_state_dict(sd, strict=True)
    missing = list(getattr(incompat, "missing_keys", []) or [])
    unexpected = list(getattr(incompat, "unexpected_keys", []) or [])
    if missing or unexpected:
        raise ValueError(f"state_dict mismatch missing={missing} unexpected={unexpected}")


def _sorted_idx_items(raw_idx_to_label: Any) -> List[Tuple[Any, Any]]:
    if isinstance(raw_idx_to_label, dict):
        def sort_key(item: Tuple[Any, Any]) -> Tuple[int, str]:
            raw_key = item[0]
            try:
                return (0, f"{int(raw_key):08d}")
            except Exception:
                try:
                    return (0, f"{int(str(raw_key)):08d}")
                except Exception:
                    return (1, str(raw_key))

        return sorted(raw_idx_to_label.items(), key=sort_key)

    if isinstance(raw_idx_to_label, list):
        return list(enumerate(raw_idx_to_label))

    raise TypeError("idx_to_label must be a list or dict")


def _label_lookup_by_key(label_lookup: Optional[Dict[str, Dict[str, Any]]], label_key: str) -> Dict[str, Any]:
    if not label_lookup:
        return {}

    value = label_lookup.get(label_key)
    if isinstance(value, dict):
        return value
    return {}


def normalize_idx_to_label(
    raw_idx_to_label: Any,
    *,
    label_lookup: Optional[Dict[str, Dict[str, Any]]],
    default_language: str,
    default_dialect: Optional[str],
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []

    for _, raw_value in _sorted_idx_items(raw_idx_to_label):
        if isinstance(raw_value, dict):
            label_key = str(
                raw_value.get("label_key")
                or raw_value.get("label_slug")
                or raw_value.get("slug")
                or ""
            ).strip()
            label_original = str(raw_value.get("label_original") or raw_value.get("label") or label_key).strip()
            label_slug = str(raw_value.get("label_slug") or raw_value.get("slug") or label_key.rsplit("/", 1)[-1]).strip()
            language = str(raw_value.get("language") or default_language).strip()
            dialect_raw = raw_value.get("dialect", default_dialect)
            dialect = None if dialect_raw is None else str(dialect_raw).strip() or None
        else:
            label_key = str(raw_value or "").strip()
            lookup = _label_lookup_by_key(label_lookup, label_key)
            label_original = str(lookup.get("label_original") or label_key).strip()
            label_slug = str(lookup.get("slug") or label_key.rsplit("/", 1)[-1]).strip()
            language = str(lookup.get("language") or default_language).strip()
            dialect_raw = lookup.get("dialect", default_dialect)
            dialect = None if dialect_raw is None else str(dialect_raw).strip() or None

        lookup = _label_lookup_by_key(label_lookup, label_key)
        if lookup:
            label_original = str(lookup.get("label_original") or label_original).strip()
            label_slug = str(lookup.get("slug") or label_slug).strip()
            language = str(lookup.get("language") or language).strip()
            dialect_raw = lookup.get("dialect", dialect)
            dialect = None if dialect_raw is None else str(dialect_raw).strip() or None

        if not label_key:
            raise ValueError("checkpoint idx_to_label contains empty label key")

        normalized.append(
            {
                "label_key": label_key,
                "label_slug": label_slug or label_key.rsplit("/", 1)[-1],
                "label_original": label_original or label_key,
                "language": language or default_language,
                "dialect": dialect,
            }
        )

    return normalized


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
    label_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
) -> ModelBundle:
    model = build_model_from_checkpoint(ckpt)
    load_weights(model, ckpt)

    idx_to_label = normalize_idx_to_label(
        ckpt["idx_to_label"],
        label_lookup=label_lookup,
        default_language=language,
        default_dialect=dialect,
    )
    validate_labels(
        idx_to_label,
        num_classes=int(ckpt["num_classes"]),
        registry_language=language,
        registry_dialect=dialect,
    )

    # Warmup lifecycle (fail-fast). Device chosen from REALTIME_DEVICE env;
    # the model stays resident on that device for inference.
    warmup_ok = False
    device = resolve_device()
    warmup(model, seq_len=int(ckpt["seq_len"]), feature_dim=int(ckpt["feature_dim"]), device=device)
    warmup_ok = True

    loaded_at = datetime.now(timezone.utc).isoformat()

    return ModelBundle(
        model_id=model_id,
        model_name=model_name,
        model=model,
        idx_to_label=idx_to_label,
        normalization_version=str(ckpt["normalization_version"]),
        preprocess_contract=dict(ckpt["preprocess_contract"]),
        checkpoint_sha256=str(checkpoint_sha256),
        checkpoint_path=str(checkpoint_path),
        language=str(language),
        dialect=dialect,
        loaded_at=loaded_at,
        warmup_ok=bool(warmup_ok),
    )
