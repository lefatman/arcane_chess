from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from .core import Game, Color, Move, Pawn, Knight, Bishop, Rook, Queen, King


_PIECE_VALUE = {
    Pawn: 100,
    Knight: 320,
    Bishop: 330,
    Rook: 500,
    Queen: 900,
    King: 0,
}

MATE_SCORE = 10_000_000


def evaluate_white(game: Game) -> int:
    """Material-only evaluation from White's perspective."""
    score = 0
    for p in game.board._pieces.values():
        v = _PIECE_VALUE.get(type(p), 0)
        score += v if p.color is Color.WHITE else -v
    return score


@dataclass
class TTEntry:
    depth: int
    value: int
    flag: str  # 'EXACT', 'LOWER', 'UPPER'
    best_uci: Optional[str] = None


class Engine:
    """Tiny alpha-beta engine for baseline chess.

    Notes:
    - Works best with a tracker attached (for transposition hashing),
      but will still work without.
    - Designed as a "good enough" demo, not a super-GM.
    """

    def __init__(self) -> None:
        self.tt: Dict[int, TTEntry] = {}

    def reset(self) -> None:
        self.tt.clear()

    def best_move(self, game: Game, depth: int = 3, time_limit_s: Optional[float] = None) -> Optional[Move]:
        deadline = None if time_limit_s is None else (time.time() + time_limit_s)
        best: Optional[Move] = None
        best_val = -10**18

        moves = game.legal_moves(game.side_to_move)
        if not moves:
            return None

        alpha = -10**18
        beta = 10**18

        # simple move ordering: captures first
        def is_capture(m: Move) -> int:
            cap = game.board.piece_at(m.to_sq)
            return 1 if cap is not None else 0

        moves.sort(key=is_capture, reverse=True)

        for m in moves:
            if deadline is not None and time.time() >= deadline:
                break
            game.push(m)
            val = -self._negamax(game, depth - 1, -beta, -alpha, 1, deadline)
            game.pop()

            if val > best_val:
                best_val = val
                best = m
            alpha = max(alpha, val)

        return best

    def _key(self, game: Game) -> Optional[int]:
        tr = getattr(game, "tracker", None)
        return None if tr is None else int(tr.hash)

    def _negamax(
        self,
        game: Game,
        depth: int,
        alpha: int,
        beta: int,
        ply: int,
        deadline: Optional[float],
    ) -> int:
        if deadline is not None and time.time() >= deadline:
            # Return a quick static eval when out of time.
            sign = 1 if game.side_to_move is Color.WHITE else -1
            return sign * evaluate_white(game)

        key = self._key(game)
        if key is not None:
            ent = self.tt.get(key)
            if ent is not None and ent.depth >= depth:
                if ent.flag == "EXACT":
                    return ent.value
                if ent.flag == "LOWER":
                    alpha = max(alpha, ent.value)
                elif ent.flag == "UPPER":
                    beta = min(beta, ent.value)
                if alpha >= beta:
                    return ent.value

        moves = game.legal_moves(game.side_to_move)
        if depth <= 0 or not moves:
            # terminal / leaf
            if not moves:
                if game.in_check(game.side_to_move):
                    return -MATE_SCORE + ply
                return 0
            sign = 1 if game.side_to_move is Color.WHITE else -1
            return sign * evaluate_white(game)

        # ordering: captures first
        def cap_score(m: Move) -> int:
            cap = game.board.piece_at(m.to_sq)
            if cap is None:
                return 0
            return _PIECE_VALUE.get(type(cap), 0)
        moves.sort(key=cap_score, reverse=True)

        orig_alpha = alpha
        best_val = -10**18

        for m in moves:
            game.push(m)
            val = -self._negamax(game, depth - 1, -beta, -alpha, ply + 1, deadline)
            game.pop()

            if val > best_val:
                best_val = val
            if val > alpha:
                alpha = val
            if alpha >= beta:
                break

        if key is not None:
            flag = "EXACT"
            if best_val <= orig_alpha:
                flag = "UPPER"
            elif best_val >= beta:
                flag = "LOWER"
            self.tt[key] = TTEntry(depth=depth, value=int(best_val), flag=flag)

        return int(best_val)
