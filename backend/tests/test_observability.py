"""Tests for Enterprise Observability (Logging, Tracing, Metrics).

Uses Mock patching exclusively to ensure zero side-effects.
Covers Data Masking (SOC 2), Prometheus export, and Trace Context (W3C).
"""
import logging
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient
import structlog
from asgi_correlation_id import correlation_id

from app.main import app
from app.logging_config import mask_sensitive_data, add_correlation_id
from app.worker import setup_structlog_context, clear_structlog_context

client = TestClient(app)


def test_structlog_data_masking_standard():
    """Verify that sensitive fields are masked before emitting JSON logs."""
    event_dict = {
        "event": "User logged in",
        "username": "admin",
        "password": "supersecretpassword123",
        "api_key": "sk-1234567890",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5...",
        "safe_field": "hello world"
    }
    
    masked = mask_sensitive_data(logging.getLogger(), "info", event_dict)
    
    assert masked["password"] == "***MASKED***"
    assert masked["api_key"] == "***MASKED***"
    assert masked["access_token"] == "***MASKED***"
    assert masked["username"] == "admin"
    assert masked["safe_field"] == "hello world"
    assert masked["event"] == "User logged in"


def test_structlog_data_masking_edge_cases():
    """Verify masking behaves safely with non-string keys and partial matches."""
    event_dict = {
        "user_password_hash": "hash123", # Contains 'password'
        "token_expires": 3600,           # Contains 'token'
        123: "not a string key",         # Integer key
        "SECRET_KEY": "mysecret",        # Uppercase matching
        "normal": "value"
    }
    
    masked = mask_sensitive_data(logging.getLogger(), "info", event_dict.copy())
    
    assert masked["user_password_hash"] == "***MASKED***"
    assert masked["token_expires"] == "***MASKED***"
    assert masked["SECRET_KEY"] == "***MASKED***"
    assert masked[123] == "not a string key"
    assert masked["normal"] == "value"


def test_add_correlation_id_processor():
    """Verify that correlation ID is injected into structlog context only if present."""
    correlation_id.set(None)
    event_dict = add_correlation_id(logging.getLogger(), "info", {"event": "test"})
    assert "request_id" not in event_dict
    
    correlation_id.set("trace-1234")
    event_dict = add_correlation_id(logging.getLogger(), "info", {"event": "test"})
    assert event_dict["request_id"] == "trace-1234"
    correlation_id.set(None)


@patch("app.metrics.collect_resources")
def test_prometheus_metrics_endpoint_standard(mock_collect):
    """Verify that /metrics returns valid Prometheus text format."""
    # Keys phải khớp đúng cái metrics.py đọc: host.get("ram_used_mb") /
    # ram_total_mb (không phải mem_*), disk.used_gb/total_gb, gpu.util_pct/vram_used_mb.
    mock_collect.return_value = {
        "host": {"cpu_pct": 45.2, "ram_used_mb": 1024, "ram_total_mb": 4096},
        "disk": {"available": True, "used_gb": 50, "total_gb": 100},
        "gpu": {"available": True, "util_pct": 80, "vram_used_mb": 4000}
    }
    
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    
    text = response.text
    assert "voya_cpu_usage_percent 45.2" in text
    assert "voya_ram_used_mb 1024.0" in text
    assert "voya_disk_used_gb 50.0" in text
    assert "voya_gpu_usage_percent 80.0" in text


@patch("app.metrics.logger")
@patch("app.metrics.collect_resources")
def test_prometheus_metrics_endpoint_missing_resources(mock_collect, mock_logger):
    """Verify edge case where GPU or Disk are completely unavailable."""
    mock_collect.return_value = {
        "host": {"cpu_pct": 10.0, "ram_used_mb": 512, "ram_total_mb": 2048},
        "disk": {"available": False}, # Unmounted
        "gpu": {"available": False}   # No GPU
    }
    
    response = client.get("/metrics")
    assert response.status_code == 200
    
    text = response.text
    # Host metrics should still be present
    assert "voya_cpu_usage_percent 10.0" in text
    
    # Missing resources should default to 0 to prevent prometheus dropouts
    assert "voya_disk_used_gb 0.0" in text
    assert "voya_gpu_usage_percent 0.0" in text
    
    # Verify that errors were logged (since they are not ignored).
    # metrics.py dùng stdlib logger → ngữ cảnh đi qua extra={...}, KHÔNG phải
    # kwargs kiểu structlog (resource=/details= sẽ ném TypeError trên stdlib).
    assert mock_logger.error.call_count == 2
    mock_logger.error.assert_any_call(
        "Hardware disconnected or not found",
        extra={"resource": "disk", "details": "Dataset volume is unavailable."},
    )
    mock_logger.error.assert_any_call(
        "Hardware disconnected or not found",
        extra={"resource": "gpu", "details": "Nvidia GPU is missing or unreadable."},
    )

@patch("app.metrics.logger")
@patch("app.metrics.collect_resources")
def test_prometheus_metrics_endpoint_missing_but_ignored(mock_collect, mock_logger):
    """Verify that ignored missing resources do not spam logs."""
    mock_collect.return_value = {
        "host": {"cpu_pct": 10.0, "mem_used_mb": 512, "mem_total_mb": 2048},
        "disk": {"available": False, "ignored": True},
        "gpu": {"available": False, "ignored": True}
    }
    
    response = client.get("/metrics")
    assert response.status_code == 200
    
    # Verify that NO errors were logged because the admin ignored them
    mock_logger.error.assert_not_called()


def test_asgi_correlation_id_middleware_no_header():
    """Verify that incoming requests without an ID get a generated UUID."""
    @app.get("/api/v1/test_trace_empty")
    def trace_endpoint():
        return {"req_id": correlation_id.get()}
        
    response = client.get("/api/v1/test_trace_empty")
    assert response.status_code == 200
    
    # A UUID4 should be generated automatically
    req_id = response.json()["req_id"]
    assert req_id is not None
    assert len(req_id) == 32 # correlation_id generates 32 char uuid by default


def test_celery_task_context_signals_with_request_id():
    """Verify that Celery tasks bind task_id and request_id to structlog context."""
    mock_task = MagicMock()
    mock_task.name = "app.tasks.dummy_task"
    
    setup_structlog_context(
        task_id="celery-task-999", 
        task=mock_task, 
        kwargs={"request_id": "api-req-123"}
    )
    
    assert correlation_id.get() == "api-req-123"
    context = structlog.contextvars.get_contextvars()
    assert context["task_id"] == "celery-task-999"
    assert context["task_name"] == "app.tasks.dummy_task"
    
    clear_structlog_context()
    assert correlation_id.get() is None
    assert structlog.contextvars.get_contextvars() == {}


def test_celery_task_context_signals_missing_request_id():
    """Verify edge case: tasks triggered without a request_id fallback to task_id."""
    mock_task = MagicMock()
    mock_task.name = "app.tasks.periodic_beat"
    
    setup_structlog_context(
        task_id="celery-task-777", 
        task=mock_task, 
        kwargs={} # No request_id provided (e.g. celery beat cron task)
    )
    
    # Fallback uses task_id as the correlation_id
    assert correlation_id.get() == "celery-task-777"
    context = structlog.contextvars.get_contextvars()
    assert context["task_id"] == "celery-task-777"
    
    clear_structlog_context()
