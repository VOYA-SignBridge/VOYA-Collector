"""V2 ORM package — importing this module registers all 37 tables on
``Base.metadata`` (Alembic env depends on that).
"""
from app.orm.base_model import Base  # noqa: F401

# Domain 1: Auth & Legal
from app.orm.auth_models import (  # noqa: F401
    LegalDocument,
    Role,
    User,
    UserConsent,
    UserProfile,
    UserSession,
)

# Domain 2: Org & Quota
from app.orm.org_models import (  # noqa: F401
    Project,
    ProjectMember,
    Workspace,
    WorkspaceMember,
    WorkspaceQuota,
)

# Domain 3: Taxonomy
from app.orm.taxonomy_models import (  # noqa: F401
    Category,
    ClassCategory,
    Dialect,
    Language,
    ProjectClass,
    SignClass,
    SignFeature,
)

# Domain 4: Devices & Sessions
from app.orm.collection_models import CollectionSession, Device  # noqa: F401

# Domain 5: Media & Infra
from app.orm.media_models import (  # noqa: F401
    ProjectSheetExport,
    RawUpload,
    Sample,
    SampleMedia,
    SampleProcessing,
    SampleSyncStatus,
)

# Domain 6: QA
from app.orm.qa_models import SampleReview  # noqa: F401

# Domain 7: MLOps
from app.orm.mlops_models import (  # noqa: F401
    Dataset,
    DatasetVersion,
    InferenceLog,
    MlModel,
    ModelArchitecture,
    ModelVersion,
    TrainingJob,
)

# Domain 8: Audit & Log
from app.orm.audit_models import (  # noqa: F401
    LogCategory,
    SystemAuditLog,
    SystemLogFile,
)

__all__ = ["Base"]
