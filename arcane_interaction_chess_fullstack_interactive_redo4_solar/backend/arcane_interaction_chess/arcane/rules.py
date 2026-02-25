from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

from ..core.rules import Rule
from ..core.types import Color, file_of, rank_of, in_bounds, sq
from ..core.moves import Move, NormalMove, EnPassantMove
from ..core.piece import Piece
from ..core.pieces import Pawn, Knight, Bishop, Rook, Queen, King
from .definitions import AbilityId, ElementId, CardinalDir
from .moves import RemoteCaptureMove

PIECE_RANK = {
    "Pawn": 1,
    "Knight": 3,
    "Bishop": 3,
    "Rook": 5,
    "Queen": 9,
    "King": 100,
}

def piece_rank(p: Piece) -> int:
    return PIECE_RANK[type(p).__name__]

def _capture_origin(move: Move, captured_sq: int) -> int:
    # for normal capture: origin is from_sq
    # for en-passant: origin is from_sq (captured is on captured_sq)
    # for remote capture: origin_sq field
    if isinstance(move, EnPassantMove):
        return move.from_sq
    if move.__class__.__name__ == "RemoteCaptureMove":
        return getattr(move, "origin_sq")
    return move.from_sq

def _direction_from_target_to_origin(target_sq: int, origin_sq: int) -> Optional[CardinalDir]:
    tf, tr = file_of(target_sq), rank_of(target_sq)
    of, or_ = file_of(origin_sq), rank_of(origin_sq)
    if tf == of:
        if or_ > tr:
            return CardinalDir.NORTH
        if or_ < tr:
            return CardinalDir.SOUTH
    if tr == or_:
        if of > tf:
            return CardinalDir.EAST
        if of < tf:
            return CardinalDir.WEST
    return None

class ChainKillRule(Rule):
    """Adds RemoteCaptureMove options for pieces that have Chain Kill equipped."""

    def apply(self, game, color: Color, moves: Iterable[Move]) -> Iterable[Move]:
        # yield base moves first
        base = list(moves)
        for m in base:
            yield m

        # must be ArcaneGame
        if not hasattr(game, "arcane_has_ability"):
            return

        attacker_el = game.player_config[color].element
        defender_el = game.player_config[color.opponent()].element

        # Earth nullifies remote offensive capture unless attacker is Fire
        if defender_el is ElementId.EARTH and attacker_el is not ElementId.FIRE:
            return

        # Fire offensive abilities ineffective vs Water armies (includes Chain Kill)
        if attacker_el is ElementId.FIRE and defender_el is ElementId.WATER:
            return

        # Add remote captures
        for p in game.board.pieces_of(color):
            if not game.arcane_has_ability(p, AbilityId.CHAIN_KILL):
                continue
            # find adjacent allies
            pf, pr = file_of(p.pos), rank_of(p.pos)
            for df in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if df == 0 and dr == 0:
                        continue
                    af, ar = pf + df, pr + dr
                    if not in_bounds(af, ar):
                        continue
                    ally_sq = sq(af, ar)
                    ally = game.board.piece_at(ally_sq)
                    if ally is None or ally.color is not color:
                        continue
                    # compute capture targets from ally_sq
                    for tgt in _virtual_capture_targets(game, p, ally_sq):
                        # only enemies
                        target_piece = game.board.piece_at(tgt)
                        if target_piece is None or target_piece.color is color:
                            continue
                        yield RemoteCaptureMove(from_sq=p.pos, to_sq=tgt, flags=("remote_capture",), origin_sq=ally_sq)

def _virtual_capture_targets(game, piece: Piece, origin_sq: int) -> List[int]:
    tname = type(piece).__name__
    origin_f, origin_r = file_of(origin_sq), rank_of(origin_sq)

    out: List[int] = []

    def add_if_enemy(to_sq: int) -> None:
        tp = game.board.piece_at(to_sq)
        if tp is not None and tp.color is not piece.color:
            out.append(to_sq)

    if isinstance(piece, Pawn):
        direction = 1 if piece.color is Color.WHITE else -1
        for df in (-1, 1):
            f, r = origin_f + df, origin_r + direction
            if in_bounds(f, r):
                add_if_enemy(sq(f, r))
        return out

    if isinstance(piece, Knight):
        for df, dr in ((1,2),(2,1),(2,-1),(1,-2),(-1,-2),(-2,-1),(-2,1),(-1,2)):
            f, r = origin_f + df, origin_r + dr
            if in_bounds(f, r):
                add_if_enemy(sq(f, r))
        return out

    # king step captures
    if isinstance(piece, King):
        for df, dr in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
            f, r = origin_f + df, origin_r + dr
            if in_bounds(f, r):
                add_if_enemy(sq(f, r))
        return out

    # sliders
    if isinstance(piece, (Bishop, Rook, Queen)):
        if isinstance(piece, Bishop):
            deltas = ((1,1),(1,-1),(-1,1),(-1,-1))
        elif isinstance(piece, Rook):
            deltas = ((1,0),(-1,0),(0,1),(0,-1))
        else:
            deltas = ((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1))

        passthrough = game.slide_can_pass_through(piece)
        for df, dr in deltas:
            f, r = origin_f + df, origin_r + dr
            while in_bounds(f, r):
                to = sq(f, r)
                tp = game.board.piece_at(to)
                if tp is not None:
                    if tp.color is not piece.color:
                        out.append(to)
                    if not passthrough:
                        break
                f += df
                r += dr
        return out

    return out

class CaptureDefenseRule(Rule):
    """Filters capture moves using defensive abilities: Block Path, Stalwart, Belligerent."""

    def apply(self, game, color: Color, moves: Iterable[Move]) -> Iterable[Move]:
        if not hasattr(game, "arcane_has_ability"):
            yield from moves
            return

        attacker_el = game.player_config[color].element
        defender_el = game.player_config[color.opponent()].element

        # Air negates defensive abilities, unless negated by Earth defender
        air_negates_defense = (attacker_el is ElementId.AIR and defender_el is not ElementId.EARTH)

        for m in moves:
            # determine captured square/piece if any
            captured_sq = m.to_sq
            if isinstance(m, EnPassantMove):
                captured_sq = m.captured_sq

            cap = game.board.piece_at(captured_sq)
            if cap is None or cap.color is color:
                yield m
                continue

            if air_negates_defense:
                yield m
                continue

            attacker = game.board.piece_at(m.from_sq)
            if attacker is None:
                continue

            # Block Path
            if game.arcane_has_ability(cap, AbilityId.BLOCK_PATH):
                blocked = cap.meta.get("block_dir")
                if blocked is not None:
                    origin = _capture_origin(m, captured_sq)
                    d = _direction_from_target_to_origin(captured_sq, origin)
                    if d is not None and d.value == blocked:
                        continue

            # Stalwart / Belligerent
            ar = piece_rank(attacker)
            dr = piece_rank(cap)

            if game.arcane_has_ability(cap, AbilityId.STALWART) and ar < dr:
                continue
            if game.arcane_has_ability(cap, AbilityId.BELLIGERENT) and ar > dr:
                continue

            yield m
