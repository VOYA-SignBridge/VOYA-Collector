"""Contract tests for the training router's schema module boundary."""

from typing import List

from app.modules.training import schemas
from app.routers import training


SCHEMA_NAMES = (
    "SplitProvenance",
    "DatasetInfo",
    "TrainingConfig",
    "TrainingJob",
    "TrainingMetrics",
    "DatasetPrepareRequest",
    "PromoteResponse",
    "TrainedModelPredictRequest",
    "TrainedModelPredictResponse",
)


def test_training_router_reexports_module_schemas() -> None:
    for name in SCHEMA_NAMES:
        assert getattr(training, name) is getattr(schemas, name)


def test_training_routes_use_extracted_response_models() -> None:
    response_models = {
        route.response_model
        for route in training.router.routes
        if getattr(route, "response_model", None) is not None
    }

    assert schemas.DatasetInfo in response_models
    assert schemas.TrainingJob in response_models
    assert List[schemas.TrainingMetrics] in response_models
    assert schemas.PromoteResponse in response_models
    assert schemas.TrainedModelPredictResponse in response_models
