"""Result Doctor: deterministic audits of how a reported result was produced."""

from .audit import audit_bundle, audit_manifest
from .bundle import Bundle
from .evidence import Grade
from .manifest import ManifestError, bundle_from_manifest
from .rules import RULE_IDS, evaluate
from .status import RuleFinding, RuleStatus, UniverseStatus, canonical_json

__version__ = "0.1.0"

__all__ = [
    "Bundle",
    "Grade",
    "ManifestError",
    "RULE_IDS",
    "RuleFinding",
    "RuleStatus",
    "UniverseStatus",
    "audit_bundle",
    "audit_manifest",
    "bundle_from_manifest",
    "canonical_json",
    "evaluate",
    "__version__",
]
