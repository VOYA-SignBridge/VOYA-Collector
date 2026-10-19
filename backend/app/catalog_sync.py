"""Compatibility facade for the dataset catalog synchronization module."""

import sys

from app.modules.dataset import catalog_sync as _implementation


sys.modules[__name__] = _implementation
