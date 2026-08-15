"""Owner decision packet writer.

OD-001 through OD-013 are ACCEPTED / FROZEN. This writer emits the frozen
record. Historical pending packets are preserved under data/metadata/historical/.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from foundation.living_cost.owner_freeze import (
    FROZEN_DECISIONS,
    write_owner_freeze_record,
)

# Backward-compatible alias. Callers that imported DECISIONS still see the
# frozen decision list (now ACCEPTED / FROZEN, not pending options).
DECISIONS: list[dict[str, Any]] = FROZEN_DECISIONS


def write_owner_decision_packet(metadata_dir: Path) -> dict[str, Any]:
    """Write the frozen owner-decision record. Headline remains unpublished."""
    return write_owner_freeze_record(metadata_dir)
