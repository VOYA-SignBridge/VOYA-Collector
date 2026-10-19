"""API schemas for the training module.

The router imports and re-exports these names so existing callers can keep
using ``app.routers.training`` while the module boundary is introduced.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


class SplitProvenance(BaseModel):
    """Cách tập dữ liệu ĐANG được chia, đọc từ split_metadata.json.

    Step 3 trước đây hiện ba thanh trượt tỉ lệ mà không gửi đi đâu: backend luôn
    dùng split đã sinh sẵn. Người dùng tưởng mình đang điều chỉnh, và quan trọng
    hơn là không biết con số cuối cùng đo trên người ký đã thấy hay người mới —
    khác biệt đo được là +0.129 độ chính xác. Model này thay thanh trượt giả bằng
    sự thật.
    """

    split_mode: Optional[str] = None
    signer_disjoint: bool = False
    signers: Dict[str, List[str]] = {}
    counts: Dict[str, int] = {}
    dataset_manifest: Optional[str] = None
    valid_for_research: Optional[bool] = None
    warning: Optional[str] = None
    is_deployment_split: bool = False


class DatasetInfo(BaseModel):
    """Thông tin dataset"""

    total_samples: int
    total_classes: int
    languages: List[str]
    dialects: Dict[str, List[str]]
    class_distribution: Dict[str, int]
    samples_by_dialect: Dict[str, int] = {}
    split_info: Optional[Dict[str, int]] = None
    split_provenance: Optional[SplitProvenance] = None


class TrainingConfig(BaseModel):
    """Cấu hình training"""

    model_type: str = "tcn"
    dialects: List[str] = []
    languages: List[str] = []
    epochs: int = 80
    batch_size: int = 32
    learning_rate: float = 0.001
    dropout: float = 0.3
    channels: int = 64
    levels: int = 3
    kernel_size: int = 5
    run_purpose: str = "smoke_test"
    split_version: Optional[str] = None
    dataset_version: Optional[str] = None
    recognition_profile: Optional[str] = None


class TrainingJob(BaseModel):
    """Thông tin training job"""

    id: str
    status: str
    config: TrainingConfig
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_epoch: int = 0
    total_epochs: int = 80
    checkpoint_path: Optional[str] = None
    test_acc: Optional[float] = None
    test_f1: Optional[float] = None
    error_message: Optional[str] = None
    promoted_at: Optional[str] = None
    split_provenance: Optional[SplitProvenance] = None


class TrainingMetrics(BaseModel):
    """Metrics trong quá trình training"""

    epoch: int
    train_loss: float
    train_acc: float
    val_loss: float
    val_acc: float
    val_f1: float
    learning_rate: Optional[float] = None


class DatasetPrepareRequest(BaseModel):
    """Người bấm chỉ chọn phương ngữ; profile suy ra từ danh mục nhãn."""

    dialects: Optional[List[str]] = None
    profiles: Optional[List[str]] = None
    seed: int = 42


class PromoteResponse(BaseModel):
    """Kết quả promote model lên realtime"""

    job: TrainingJob
    model_id: str
    deployed_checkpoint: str
    registry_updated: bool
    realtime_reloaded: bool
    message: str


class TrainedModelPredictRequest(BaseModel):
    """Request to predict using trained model"""

    frames: List[List[float]]


class TrainedModelPredictResponse(BaseModel):
    """Prediction response from trained model"""

    label: str
    confidence: float
    label_key: str
