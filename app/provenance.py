from __future__ import annotations

from enum import Enum


class Provenance(str, Enum):
    provider = "provider"
    user_submitted = "user_submitted"
    synthetic_experimental = "synthetic_experimental"
    computed_geometry = "computed_geometry"
    model_estimate = "model_estimate"
    unavailable = "unavailable"


class EvidenceState(str, Enum):
    scored = "scored"
    insufficient_evidence = "insufficient_evidence"
    unavailable = "unavailable"


PROVENANCE_TAGS = frozenset(item.value for item in Provenance)
