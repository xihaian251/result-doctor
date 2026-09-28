"""Loaders for the two frozen archives Phase 1 is scoped to.

Each loader maps already-frozen evidence onto the schema. Neither discovers projects,
scans repositories, talks to a tracker, nor parses a PDF.
"""

from .gmmvi import load_gmmvi_bundle
from .torchssl import load_torchssl_bundle

__all__ = ["load_gmmvi_bundle", "load_torchssl_bundle"]
