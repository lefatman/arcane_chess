from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from ..core.types import Color
from ..arcane.game import ArcaneGame
from ..arcane.loadout import PlayerConfig, AbilitySlot
from ..arcane.definitions import ElementId, ItemId, AbilityId

from .serde import snapshot, dict_to_move, move_to_dict, move_to_uci

from ..san import to_san


def _index_by_uid(snap: Dict[str, Any]) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    for p in snap.get("pieces", []):
        out[int(p["uid"])] = p
    return out


def diff(before: Dict[str, Any], after: Dict[str, Any]) -> Dict[str, Any]:
    """Compute an animation-friendly diff between two snapshots."""
    b = _index_by_uid(before)
    a = _index_by_uid(after)

    added = [a_uid for a_uid in a.keys() if a_uid not in b]
    removed = [b_uid for b_uid in b.keys() if b_uid not in a]

    moved: List[Dict[str, Any]] = []
    meta_changed: List[Dict[str, Any]] = []

    for uid in a.keys() & b.keys():
        bp = b[uid]
        ap = a[uid]
        if int(bp["pos"]) != int(ap["pos"]):
            moved.append({
                "uid": uid,
                "from": int(bp["pos"]),
                "to": int(ap["pos"]),
                "from_alg": bp["pos_alg"],
                "to_alg": ap["pos_alg"],
                "type": ap["type"],
                "color": ap["color"],
            })
        if bp.get("meta", {}) != ap.get("meta", {}):
            meta_changed.append({
                "uid": uid,
                "type": ap["type"],
                "color": ap["color"],
                "before": bp.get("meta", {}),
                "after": ap.get("meta", {}),
            })

    return {
        "added": [a[uid] for uid in added],
        "removed": [b[uid] for uid in removed],
        "moved": moved,
        "meta_changed": meta_changed,
        "side_to_move": after.get("side_to_move"),
        "last_move": after.get("last_move"),
    }


class ArcaneEngine:
    """A small, stable facade for UI/server integration.

    - apply/undo are deterministic
    - returns snapshots + diffs for animation
    """

    def __init__(
        self,
        white: PlayerConfig,
        black: PlayerConfig,
        rng_seed: int = 1337,
    ) -> None:
        self.game = ArcaneGame(white=white, black=black, rng_seed=rng_seed)

    @classmethod
    def standard_demo_game(cls) -> "ArcaneEngine":
        """Creates a normal chess setup with no arcane powers (baseline)."""
        w = PlayerConfig(element=ElementId.EARTH, items=[], abilities=[])
        b = PlayerConfig(element=ElementId.EARTH, items=[], abilities=[])
        eng = cls(w, b)
        eng.game.setup_standard()
        eng.game.attach_tracker()
        return eng

    def state(self) -> Dict[str, Any]:
        return snapshot(self.game)

    def legal_moves(self, color: Optional[str] = None) -> List[Dict[str, Any]]:
        if color is None:
            c = self.game.side_to_move
        else:
            c = Color.WHITE if color.upper() == "WHITE" else Color.BLACK
        return [move_to_dict(m) for m in self.game.legal_moves(c)]

    def _notation_for_move_in_position(self, move_obj) -> Dict[str, Any]:
        # SAN needs the *pre*-move position. We temporarily apply the standard
        # trick: pop the move quietly, compute SAN, then re-apply quietly.
        return {"uci": move_to_uci(move_obj), "san": to_san(self.game, move_obj)}

    def _notation_for_last_move(self) -> Optional[Dict[str, Any]]:
        lm = self.game.last_move
        if lm is None or not getattr(self.game, "_stack", None):
            return None
        # pop to get pre-state
        self.game.pop_quiet()
        try:
            return {"uci": move_to_uci(lm), "san": to_san(self.game, lm), "move": move_to_dict(lm)}
        finally:
            self.game.push_quiet(lm)

    def _gather_effects(self) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []

        # transient effects (Redo, etc.)
        for e in getattr(self.game, "transient_effects", []) or []:
            ee = dict(e)
            # JSONify move objects if present
            if "forbidden" in ee and ee["forbidden"] is not None:
                ee["forbidden"] = move_to_dict(ee["forbidden"])
            if "replay" in ee and ee["replay"] is not None:
                ee["replay"] = move_to_dict(ee["replay"])
            out.append(ee)

        # per-ply effects for the last applied ply (if any)
        if getattr(self.game, "_stack", None):
            last_undo = self.game._stack[-1]
            for e in last_undo.extras.get("effects", []) or []:
                out.append(dict(e))

        return out

    def apply(self, move: Dict[str, Any]) -> Dict[str, Any]:
        before = snapshot(self.game)
        m = dict_to_move(move)

        # Notation for the user-submitted move in the current position
        applied_notation = {"uci": move_to_uci(m), "san": to_san(self.game, m)}

        self.game.push(m)
        after = snapshot(self.game)
        d = diff(before, after)

        meta = {
            "applied": move_to_dict(m),
            "applied_notation": applied_notation,
            "result_last_move": after.get("last_move"),
            "result_last_notation": self._notation_for_last_move(),
            "effects": self._gather_effects(),
            "check": after.get("check"),
            "checkmate": after.get("checkmate"),
        }

        return {"before": before, "after": after, "diff": d, "meta": meta}

    def undo(self) -> Dict[str, Any]:
        before = snapshot(self.game)

        # Capture metadata about what we're undoing
        undone_move = self.game.last_move
        undone_meta = None
        if undone_move is not None and getattr(self.game, "_stack", None):
            last_undo = self.game._stack[-1]
            undone_meta = {
                "move": move_to_dict(undone_move),
                "uci": move_to_uci(undone_move),
                # SAN of undone move needs the pre-state, so compute by popping quietly.
            }
            self.game.pop_quiet()
            try:
                undone_meta["san"] = to_san(self.game, undone_move)
            finally:
                self.game.push_quiet(undone_move)
            undone_meta["effects"] = [dict(e) for e in last_undo.extras.get("effects", []) or []]

        self.game.pop()
        after = snapshot(self.game)
        return {"before": before, "after": after, "diff": diff(before, after), "meta": {"undone": undone_meta}}
