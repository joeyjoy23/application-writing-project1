"""Teaching Flow Orchestrator — safe classroom rhythm pass on slide specs only."""

from __future__ import annotations

import copy
from typing import Any

# Dangerous merges (phrase body+footer, essay+批注, vocab tier collapse, sparse-page
# stacking) are disabled. Vocab row pagination runs in pack_slides after this pass.


def orchestrate_teaching_flow(slides: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pass-through: preserve separate phrase/essay/vocab specs; no table/content merges."""
    return [copy.deepcopy(spec) for spec in slides]


__all__ = ["orchestrate_teaching_flow"]
