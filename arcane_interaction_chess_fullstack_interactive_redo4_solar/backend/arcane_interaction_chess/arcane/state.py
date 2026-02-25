from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..core.types import Color

@dataclass
class ArcaneState:
    # redo: per-piece charges (NOT undone by rewind; monotonic)
    redo_charges: Dict[int, int] = field(default_factory=dict)     # piece.uid -> remaining
    redo_max: Dict[int, int] = field(default_factory=dict)         # piece.uid -> max

    # necromancer: per-side pool (undoable on normal pop / redo rewind)
    #
    # Solar Necklace can "top up" consumables. To keep Solar effects stable across
    # Redo rewinds (which pop plies and restore undoable state), we track a
    # monotonic bonus that is NOT part of the undoable snapshot.
    # Undoable snapshots store base values (pool/max minus bonus), and restore
    # recomposes base + current bonus.
    necro_pool: Dict[Color, int] = field(default_factory=lambda: {Color.WHITE: 0, Color.BLACK: 0})
    necro_max: Dict[Color, int] = field(default_factory=lambda: {Color.WHITE: 0, Color.BLACK: 0})
    necro_bonus: Dict[Color, int] = field(default_factory=lambda: {Color.WHITE: 0, Color.BLACK: 0})

    # solar necklace: per-side uses remaining.
    # NOTE: Solar uses are NOT part of the undoable snapshot; they are treated as
    # a match-level consumable that persists across Redo rewinds.
    solar_uses: Dict[Color, int] = field(default_factory=lambda: {Color.WHITE: 0, Color.BLACK: 0})
    SOLAR_MAX_USES: int = 3

    # graveyard: captured friendly pieces with their capture squares (undoable)
    graveyard: Dict[Color, List[Tuple[object, int]]] = field(default_factory=lambda: {Color.WHITE: [], Color.BLACK: []})

    def snapshot_undoable(self) -> dict:
        return {
            # Store base values (minus any monotonic bonus).
            "necro_pool_base": {c: int(self.necro_pool[c] - self.necro_bonus[c]) for c in self.necro_pool},
            "necro_max_base": {c: int(self.necro_max[c] - self.necro_bonus[c]) for c in self.necro_max},
            "graveyard": {
                c: list(self.graveyard[c]) for c in self.graveyard
            }
        }

    def restore_undoable(self, snap: dict) -> None:
        # Recompose base + current bonus.
        base_pool = dict(snap["necro_pool_base"])
        base_max = dict(snap["necro_max_base"])
        self.necro_pool = {c: int(base_pool[c] + self.necro_bonus[c]) for c in base_pool}
        self.necro_max = {c: int(base_max[c] + self.necro_bonus[c]) for c in base_max}
        self.graveyard = {c: list(snap["graveyard"][c]) for c in snap["graveyard"]}
