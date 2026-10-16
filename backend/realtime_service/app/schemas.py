from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, root_validator, validator


class FeatureLayout(BaseModel):
    type: str = Field(..., description="Semantic feature layout type, e.g. hands_126")
    slots: List[str] = Field(..., min_items=1)
    handedness_policy: str = Field(...)

    coordinate_space: str = Field(..., description="e.g. mediapipe_normalized")
    coordinate_order: str = Field(..., description="e.g. xyz")
    frontend_mirroring: str = Field(..., description="e.g. visual_only")
    missing_hands_policy: str = Field(..., description="e.g. zero_filled_by_frontend")


class PreprocessContract(BaseModel):
    feature_layout: FeatureLayout
    expects_strict_shape: Tuple[int, int] = Field(..., description="Strict expected (T,D)")


class RegistryModelEntry(BaseModel):
    id: str
    name: str

    checkpoint_path: str
    language: str
    dialect: Optional[str] = None

    seq_len: int
    feature_dim: int

    normalization_version: str
    preprocess_contract: PreprocessContract

    # Optional nice-to-have: registry pins expected semantic contract hash
    expected_contract_hash: Optional[str] = None

    @validator("id", "name", "checkpoint_path", "language", pre=True)
    def _non_empty_str(cls, v: Any) -> str:
        s = str(v or "").strip()
        if not s:
            raise ValueError("must be non-empty")
        return s

    @validator("dialect", pre=True)
    def _dialect_nullable(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


class ModelRegistry(BaseModel):
    schema_version: str
    models: List[RegistryModelEntry]

    @root_validator
    def _validate_models_non_empty(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        models = values.get("models")
        if not models:
            raise ValueError("registry has no models; refusing to start")
        return values


class LabelSpec(BaseModel):
    # NOTE: chosen as structured objects (Option B)
    label_key: str
    label_slug: str
    label_original: str
    language: str
    dialect: Optional[str] = None

    @validator("label_key", "label_slug", "label_original", "language", pre=True)
    def _non_empty(cls, v: Any) -> str:
        s = str(v or "").strip()
        if not s:
            raise ValueError("must be non-empty")
        # reject obvious control chars
        if any(ord(ch) < 32 for ch in s):
            raise ValueError("contains control characters")
        return s

    @validator("dialect", pre=True)
    def _dialect_nullable(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        s = str(v).strip()
        return s or None


class PredictRequest(BaseModel):
    model_id: str
    frames: List[List[float]]

    @validator("model_id", pre=True)
    def _model_id_non_empty(cls, v: Any) -> str:
        s = str(v or "").strip()
        if not s:
            raise ValueError("model_id must be non-empty")
        return s

    @root_validator
    def _validate_frames_shape(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        frames = values.get("frames")
        if not isinstance(frames, list):
            raise ValueError("frames must be a list")
        if len(frames) != 60:
            raise ValueError(f"frames must have length 60, got {len(frames)}")
        for i, frame in enumerate(frames):
            if not isinstance(frame, list):
                raise ValueError(f"frames[{i}] must be a list, got {type(frame).__name__}")
            if len(frame) != 126:
                raise ValueError(f"frames[{i}] must have length 126, got {len(frame)}")
            for j, val in enumerate(frame):
                try:
                    f = float(val)
                    if not (f == f):
                        raise ValueError(f"frames[{i}][{j}] is NaN")
                    if f == float("inf") or f == float("-inf"):
                        raise ValueError(f"frames[{i}][{j}] is infinite")
                except (TypeError, ValueError) as e:
                    if "NaN" in str(e) or "infinite" in str(e):
                        raise
                    raise ValueError(f"frames[{i}][{j}] is not numeric: {e}")
        return values


class PredictResponse(BaseModel):
    label: str
    confidence: float
    label_key: str

    @validator("label", "label_key", pre=True)
    def _non_empty_str(cls, v: Any) -> str:
        s = str(v or "").strip()
        if not s:
            raise ValueError("must be non-empty")
        return s

    @validator("confidence", pre=True)
    def _confidence_bounded(cls, v: Any) -> float:
        f = float(v)
        if not (f == f):
            raise ValueError("confidence must be finite")
        if f == float("inf") or f == float("-inf"):
            raise ValueError("confidence must be finite")
        if not (0.0 <= f <= 1.0):
            raise ValueError(f"confidence must be in [0, 1], got {f}")
        return f
