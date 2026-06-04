"""Amp B-1 Activation Engine.

Pipeline package for gathering vault signals, extracting candidate offers,
ranking them, producing grounded drafts, logging responses, and replaying
sanitized fixtures for calibration.
"""

from .config import load_config, load_weights, load_kill, load_quiet

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "load_config",
    "load_weights",
    "load_kill",
    "load_quiet",
]
