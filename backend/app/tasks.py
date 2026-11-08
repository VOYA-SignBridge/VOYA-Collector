"""Compatibility facade for the dataset video-processing Celery task."""

import sys

from app.modules.dataset import video_tasks as _implementation

sys.modules[__name__] = _implementation
