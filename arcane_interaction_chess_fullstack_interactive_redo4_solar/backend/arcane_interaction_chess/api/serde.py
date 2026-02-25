from __future__ import annotations

from dataclasses import asdict
import logging
from typing import Any, Dict, List, Optional, Tuple, Type

from ..core.types import Color, sq_name, FILES
from ..core.moves import (
    Move,
    NormalMove,
    EnPassantMove,
    CastleMove,
    PromotionMove,
)

# Arcane move
try:
    from ..arcane.moves import RemoteCaptureMove  # type: ignore
except ImportError:  # pragma: no cover
    RemoteCaptureMove = None  # type: ignore

from ..core import pieces as core_pieces


LOGGER = logging.getLogger("arcane.api.serde")


_PIECE_NAME_TO_CLASS: Dict[str, Type] = {
    "Queen": core_pieces.Queen,
    "Rook": core_pieces.Rook,
    "Bishop": core_pieces.Bishop,
    "Knight": core_pieces.Knight,
}


def _color_to_str(c: Color) -> str:
    return "WHITE" if c is Color.WHITE else "BLACK"


def _sq_to_alg(s: int) -> str:
    return sq_name(s)


def _alg_to_sq(a: str) -> int:
    a = a.strip().lower()
    if len(a) != 2:
        raise ValueError(f"Bad square: {a!r}")
    f = FILES.index(a[0])
    r = int(a[1]) - 1
    if not (0 <= f < 8 and 0 <= r < 8):
        raise ValueError(f"Bad square: {a!r}")
    return r * 8 + f


def move_to_dict(m: Move) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "from": m.from_sq,
        "to": m.to_sq,
        "from_alg": _sq_to_alg(m.from_sq),
        "to_alg": _sq_to_alg(m.to_sq),
        "flags": list(getattr(m, "flags", ()) or ()),
    }

    if isinstance(m, NormalMove):
        d["kind"] = "normal"
    elif isinstance(m, EnPassantMove):
        d["kind"] = "en_passant"
        d["captured_sq"] = m.captured_sq
        d["captured_alg"] = _sq_to_alg(m.captured_sq)
    elif isinstance(m, CastleMove):
        d["kind"] = "castle"
        d["rook_from"] = m.rook_from
        d["rook_to"] = m.rook_to
        d["rook_from_alg"] = _sq_to_alg(m.rook_from)
        d["rook_to_alg"] = _sq_to_alg(m.rook_to)
    elif isinstance(m, PromotionMove):
        d["kind"] = "promotion"
        promote_cls = m.promote_to
        d["promote_to"] = getattr(promote_cls, "__name__", "Queen")
    else:
        # Arcane remote capture
        if RemoteCaptureMove is not None and isinstance(m, RemoteCaptureMove):
            d["kind"] = "remote_capture"
            d["origin_sq"] = m.origin_sq
            d["origin_alg"] = _sq_to_alg(m.origin_sq)
        else:
            d["kind"] = m.__class__.__name__

    return d


def move_to_uci(m: Move) -> str:
    """Return a UCI-style string.

    For arcane remote captures, we append "@<origin>" to keep it lossless.
    """
    fr = _sq_to_alg(m.from_sq)
    to = _sq_to_alg(m.to_sq)
    promo = ""
    if isinstance(m, PromotionMove):
        name = getattr(m.promote_to, "__name__", "Queen")
        promo = name[0].lower()  # q/r/b/n

    # remote capture suffix
    if RemoteCaptureMove is not None and isinstance(m, RemoteCaptureMove):
        return f"{fr}{to}{promo}@{_sq_to_alg(m.origin_sq)}"

    return f"{fr}{to}{promo}"


def dict_to_move(d: Dict[str, Any]) -> Move:
    kind = d.get("kind", "normal")

    def get_sq(key_num: str, key_alg: str) -> int:
        if key_num in d:
            return int(d[key_num])
        if key_alg in d:
            return _alg_to_sq(str(d[key_alg]))
        raise ValueError(f"Missing square: {key_num}/{key_alg}")

    fr = get_sq("from", "from_alg")
    to = get_sq("to", "to_alg")
    flags = tuple(d.get("flags", []) or [])

    if kind == "normal":
        return NormalMove(fr, to, flags=flags)

    if kind == "en_passant":
        csq = int(d.get("captured_sq")) if "captured_sq" in d else _alg_to_sq(d["captured_alg"])
        return EnPassantMove(fr, to, flags=flags, captured_sq=csq)

    if kind == "castle":
        rf = int(d.get("rook_from")) if "rook_from" in d else _alg_to_sq(d["rook_from_alg"])
        rt = int(d.get("rook_to")) if "rook_to" in d else _alg_to_sq(d["rook_to_alg"])
        return CastleMove(fr, to, flags=flags, rook_from=rf, rook_to=rt)

    if kind == "promotion":
        name = str(d.get("promote_to", "Queen"))
        cls = _PIECE_NAME_TO_CLASS.get(name, core_pieces.Queen)
        return PromotionMove(fr, to, flags=flags, promote_to=cls)

    if kind == "remote_capture":
        if RemoteCaptureMove is None:
            raise ValueError("RemoteCaptureMove not available")
        origin = int(d.get("origin_sq")) if "origin_sq" in d else _alg_to_sq(d["origin_alg"])
        return RemoteCaptureMove(fr, to, flags=flags, origin_sq=origin)

    raise ValueError(f"Unknown move kind: {kind!r}")


def snapshot(game) -> Dict[str, Any]:
    """JSON-friendly snapshot of current match state."""

    pieces: List[Dict[str, Any]] = []
    for p in game.board._pieces.values():
        pieces.append(
            {
                "uid": p.uid,
                "color": _color_to_str(p.color),
                "type": type(p).__name__,
                "pos": p.pos,
                "pos_alg": _sq_to_alg(p.pos),
                "has_moved": bool(p.has_moved),
                "meta": dict(p.meta),
                "symbol": p.symbol,
            }
        )

    out: Dict[str, Any] = {
        "side_to_move": _color_to_str(game.side_to_move),
        "last_move": move_to_dict(game.last_move) if game.last_move is not None else None,
        "pieces": sorted(pieces, key=lambda x: (x["color"], x["type"], x["pos"])),
        "ply": len(getattr(game, "_stack", [])),
        "halfmove_clock": int(getattr(game, "halfmove_clock", 0)),
        "fullmove_number": int(getattr(game, "fullmove_number", 1)),
    }

    # check / mate convenience flags for UI
    try:
        stm = game.side_to_move
        in_check = bool(game.in_check(stm))
        out["check"] = in_check
        out["checkmate"] = bool(in_check and len(game.legal_moves(stm)) == 0)
    except (AttributeError, TypeError, ValueError) as exc:
        out["check"] = False
        out["checkmate"] = False
        LOGGER.warning("snapshot_check_flags_fallback", extra={"error": str(exc)})

    # FEN convenience
    try:
        from ..fen import game_to_fen  # lazy import
        out["fen"] = game_to_fen(game)
    except (ImportError, AttributeError, TypeError, ValueError) as exc:
        out["fen"] = None
        LOGGER.warning("snapshot_fen_fallback", extra={"error": str(exc)})

    # Arcane layer (if present)
    if hasattr(game, "player_config"):
        cfg = game.player_config
        out["arcane"] = {
            "WHITE": {
                "element": getattr(cfg[Color.WHITE].element, "name", str(cfg[Color.WHITE].element)),
                "element_id": int(cfg[Color.WHITE].element.value),
                "items": [int(i.value) for i in cfg[Color.WHITE].items],
                "abilities": [
                    {"ability": int(s.ability.value), "piece_type": s.piece_type}
                    for s in cfg[Color.WHITE].abilities
                ],
            },
            "BLACK": {
                "element": getattr(cfg[Color.BLACK].element, "name", str(cfg[Color.BLACK].element)),
                "element_id": int(cfg[Color.BLACK].element.value),
                "items": [int(i.value) for i in cfg[Color.BLACK].items],
                "abilities": [
                    {"ability": int(s.ability.value), "piece_type": s.piece_type}
                    for s in cfg[Color.BLACK].abilities
                ],
            },
        }

    if hasattr(game, "arcane_state"):
        st = game.arcane_state
        # graveyard is object identities; serialize by uid/type + capture square
        def gy(color: Color) -> List[Dict[str, Any]]:
            arr = []
            for obj, cap_sq in st.graveyard[color]:
                p = obj
                uid = getattr(p, "uid", None)
                arr.append(
                    {
                        "uid": uid,
                        "type": type(p).__name__,
                        "capture_sq": cap_sq,
                        "capture_alg": _sq_to_alg(cap_sq),
                    }
                )
            return arr

        out["arcane_state"] = {
            "redo_charges": dict(st.redo_charges),
            "redo_max": dict(st.redo_max),
            "necro_pool": {"WHITE": int(st.necro_pool[Color.WHITE]), "BLACK": int(st.necro_pool[Color.BLACK])},
            "necro_max": {"WHITE": int(st.necro_max[Color.WHITE]), "BLACK": int(st.necro_max[Color.BLACK])},
            "solar_uses": {"WHITE": int(st.solar_uses[Color.WHITE]), "BLACK": int(st.solar_uses[Color.BLACK])},
            "solar_max": int(st.SOLAR_MAX_USES),
            "graveyard": {"WHITE": gy(Color.WHITE), "BLACK": gy(Color.BLACK)},
        }

    return out
