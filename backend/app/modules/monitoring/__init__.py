"""Operational resource monitoring for the web system."""

from app.modules.monitoring.gpu import start_gpu_monitor
from app.modules.monitoring.service import collect_resources

__all__ = ["collect_resources", "start_gpu_monitor"]
