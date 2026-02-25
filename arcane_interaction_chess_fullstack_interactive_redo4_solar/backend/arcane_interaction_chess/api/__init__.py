"""Stable backend boundary for a future frontend.

This layer is intentionally **frontend-agnostic** and only speaks JSON-friendly
structures:
- state snapshots
- move encode/decode
- apply/undo producing diffs suitable for animation
"""

from .facade import ArcaneEngine
from .serde import move_to_dict, dict_to_move, snapshot, move_to_uci

__all__ = ["ArcaneEngine", "move_to_dict", "dict_to_move", "snapshot", "move_to_uci"]
