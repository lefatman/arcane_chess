from __future__ import annotations

import random
from typing import Dict, List, Optional, Set

from ..core.game import Game
from ..core.rules import KingSafetyRule
from ..core.types import Color
from ..core.piece import Piece
from ..core.setup import setup_standard
from ..core.tracker import PositionTracker

from .definitions import AbilityId, ElementId, ItemId, DEFENSIVE_ABILITIES, OFFENSIVE_ABILITIES
from .loadout import PlayerConfig
from .decisions import DecisionProvider, DefaultDecisions
from .state import ArcaneState
from .rules import ChainKillRule, CaptureDefenseRule

class ArcaneGame(Game):
    def __init__(
        self,
        white: PlayerConfig,
        black: PlayerConfig,
        decisions: Optional[DecisionProvider] = None,
        rng_seed: int = 1337,
    ) -> None:
        super().__init__()

        white.validate()
        black.validate()

        self.player_config: Dict[Color, PlayerConfig] = {Color.WHITE: white, Color.BLACK: black}
        self.decisions: DecisionProvider = decisions if decisions is not None else DefaultDecisions()
        self.rng = random.Random(rng_seed)
        self.arcane_state = ArcaneState()

        # Transient, per-apply semantic effects log.
        # This is consumed by the API facade to provide animation-friendly metadata.
        # It is cleared for the outermost push() only (nested pushes, e.g. Redo replay,
        # keep the log intact).
        self.transient_effects: List[dict] = []
        self._push_depth: int = 0

        # install arcane rules (then king safety)
        self.rules = [ChainKillRule(), CaptureDefenseRule(), KingSafetyRule()]

        # attach arcane system listener
        from .system import ArcaneResolutionSystem
        self.listeners.append(ArcaneResolutionSystem(self, self.decisions, self.rng))

    def push(self, move) -> None:  # type: ignore[override]
        # Clear transient effects for normal top-level pushes, but preserve them while a Redo
        # decision is pending so the frontend can animate/describe the rewind coherently.
        if self._push_depth == 0 and getattr(self, "_pending_redo", None) is None:
            self.transient_effects.clear()
        self._push_depth += 1
        try:
            super().push(move)
        finally:
            self._push_depth -= 1

    def setup_standard(self) -> None:
        setup_standard(self)
        # optional tracker: attach after setup if desired
        self.bootstrap_resources()

    def attach_tracker(self, seed: int = 0xC0FFEE) -> PositionTracker:
        tr = PositionTracker(seed=seed)
        tr.attach(self)
        return tr

    # --- arcane hooks for core engine / arcane moves ---
    def slide_can_pass_through(self, mover: Piece) -> bool:
        attacker_el = self.player_config[mover.color].element
        defender_el = self.player_config[mover.color.opponent()].element
        # Air passives negated by Earth armies
        if attacker_el is ElementId.AIR and defender_el is not ElementId.EARTH:
            return True
        return False

    def arcane_remote_capture_should_capture(self, mover: Piece, origin_sq: int, target: Piece) -> bool:
        attacker_el = self.player_config[mover.color].element
        defender_el = self.player_config[target.color].element

        # Earth nullifies remote offensive capture abilities unless attacker is Fire
        if defender_el is ElementId.EARTH and attacker_el is not ElementId.FIRE:
            return False

        # Fire offensive abilities ineffective vs Water armies (includes Chain Kill)
        if attacker_el is ElementId.FIRE and defender_el is ElementId.WATER:
            return False

        # Lightning abilities have 50% chance to misfire vs Air (including Chain Kill capture itself)
        if attacker_el is ElementId.LIGHTNING and defender_el is ElementId.AIR:
            return self.rng.random() >= 0.5

        return True

    # --- ability queries ---
    def arcane_has_ability(self, piece: Piece, ability: AbilityId) -> bool:
        cfg = self.player_config[piece.color]
        ptype = type(piece).__name__
        for slot in cfg.abilities:
            if slot.ability is not ability:
                continue
            if slot.piece_type is None or slot.piece_type == ptype:
                return True
        return False

    def arcane_abilities_for_piece(self, piece: Piece) -> Set[AbilityId]:
        cfg = self.player_config[piece.color]
        ptype = type(piece).__name__
        out: Set[AbilityId] = set()
        for slot in cfg.abilities:
            if slot.piece_type is None or slot.piece_type == ptype:
                out.add(slot.ability)
        return out

    # --- resource bootstrapping ---
    def bootstrap_resources(self) -> None:
        # solar necklace uses (undoable)
        for color in (Color.WHITE, Color.BLACK):
            cfg = self.player_config[color]
            self.arcane_state.solar_uses[color] = (
                self.arcane_state.SOLAR_MAX_USES if cfg.has_item(ItemId.SOLAR_NECKLACE) else 0
            )

        # necromancer pool base is 1 if slotted anywhere; else 0
        for color in (Color.WHITE, Color.BLACK):
            cfg = self.player_config[color]
            opponent = self.player_config[color.opponent()]
            has_necro = any(s.ability is AbilityId.NECROMANCER for s in cfg.abilities)
            base_pool = 1 if has_necro else 0

            # Water doubling (negated vs Lightning)
            if cfg.element is ElementId.WATER and opponent.element is not ElementId.LIGHTNING:
                base_pool *= 2

            self.arcane_state.necro_pool[color] = base_pool
            self.arcane_state.necro_max[color] = base_pool

        # redo charges per piece: 1, doubled for Water vs non-Lightning, but only for pieces with Redo equipped
        for p in list(self.board._pieces.values()):
            if not self.arcane_has_ability(p, AbilityId.REDO):
                continue

            cfg = self.player_config[p.color]
            opponent = self.player_config[p.color.opponent()]
            mx = 1
            if cfg.element is ElementId.WATER and opponent.element is not ElementId.LIGHTNING:
                mx = 2
            self.arcane_state.redo_max.setdefault(p.uid, mx)
            self.arcane_state.redo_charges.setdefault(p.uid, mx)

    # --- undo integration for arcane undoable state ---
    def _after_unapply(self, undo) -> None:
        snap = undo.extras.get("arcane_undoable")
        if snap is not None:
            self.arcane_state.restore_undoable(snap)
