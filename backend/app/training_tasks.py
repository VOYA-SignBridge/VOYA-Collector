"""Compatibility facade for the training task module."""

import sys

from app.modules.training import tasks as _implementation


sys.modules[__name__] = _implementation
