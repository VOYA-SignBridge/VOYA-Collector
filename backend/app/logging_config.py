import logging
from app.config import settings

def configure_logging():
    configured_level = str(getattr(settings, "log_level", "INFO")).upper()
    level = getattr(logging, configured_level, logging.INFO)
    if settings.debug_logging:
        level = logging.DEBUG
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if settings.debug_logging:
        logging.getLogger(__name__).debug("Debug logging enabled")
