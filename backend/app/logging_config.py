import logging
import sys
import structlog
from asgi_correlation_id import correlation_id
from typing import Dict, Any
from app.config import settings

def mask_sensitive_data(logger: logging.Logger, log_method: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Mask sensitive information in logs before they are emitted."""
    sensitive_keys = {"password", "token", "secret", "api_key", "access_token"}
    for key, value in event_dict.items():
        if isinstance(key, str) and any(s in key.lower() for s in sensitive_keys):
            event_dict[key] = "***MASKED***"
    return event_dict

def add_correlation_id(logger: logging.Logger, log_method: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Add correlation ID to every log line if available."""
    if req_id := correlation_id.get():
        event_dict["request_id"] = req_id
    return event_dict

# Processors every record passes through, whether it originated from structlog
# or from the standard library. Shared so a `logging.getLogger(__name__).info()`
# call and a `structlog.get_logger().info()` call produce the same shape.
_SHARED_PROCESSORS = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_log_level,
    structlog.stdlib.add_logger_name,
    structlog.processors.TimeStamper(fmt="iso"),
    add_correlation_id,
    mask_sensitive_data,
]

# Loggers that ship their own handlers. Left alone they would emit a second,
# unformatted copy of every line beside ours.
_HIJACKED_LOGGERS = (
    "uvicorn",
    "uvicorn.error",
    "uvicorn.access",
    "gunicorn",
    "gunicorn.error",
    "gunicorn.access",
    "celery",
    "celery.app.trace",
)


def configure_logging():
    """Initialize structured JSON logging.

    Note the split between the two processor lists below. `structlog.configure`
    only governs loggers obtained via `structlog.get_logger()`; a plain
    `logging.getLogger(__name__)` never touches it. This codebase logs through
    the standard library in ~46 modules and through structlog in essentially
    none, so terminating the structlog chain in a JSONRenderer (as this used to)
    left every real log line as unstructured text — promtail's `json:` stage
    then had nothing to parse and the `level` / `request_id` / `task_id` labels
    never reached Loki, which is precisely what structlog and
    asgi-correlation-id were added for.

    The fix is to render in a stdlib *formatter* instead: structlog hands its
    events to `ProcessorFormatter` rather than rendering them itself, and that
    same formatter runs foreign (stdlib) records through `foreign_pre_chain`
    first. Both paths converge on one JSON renderer attached to the root
    handler, so every module's output is structured without touching 46 files.
    """
    configured_level = str(getattr(settings, "log_level", "INFO")).upper()
    level = getattr(logging, configured_level, logging.INFO)
    if settings.debug_logging:
        level = logging.DEBUG

    structlog.configure(
        # Hand off to ProcessorFormatter instead of rendering here.
        processors=_SHARED_PROCESSORS + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # Applied only to records that did NOT come from structlog.
        foreign_pre_chain=_SHARED_PROCESSORS,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            # Without this the renderer receives the raw (type, value, traceback)
            # tuple and JSON-encodes it as reprs — "<traceback object at 0x…>",
            # i.e. every logger.exception() reaches Loki with its stack trace
            # thrown away. Render it to an "exception" string first.
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Replace rather than append: configure_logging() runs at import time in
    # main.py, worker.py and init_db.py, and a Celery child re-runs it after
    # fork. Appending would emit one duplicate line per extra call.
    root = logging.getLogger()
    for existing in root.handlers[:]:
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)

    for name in _HIJACKED_LOGGERS:
        log = logging.getLogger(name)
        log.handlers.clear()
        log.propagate = True

    if settings.debug_logging:
        structlog.get_logger(__name__).debug("Debug logging enabled")
