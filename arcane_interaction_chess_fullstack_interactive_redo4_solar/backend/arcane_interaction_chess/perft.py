from __future__ import annotations

from typing import Dict

from .core import Game
from .uci import move_to_uci


def perft(game: Game, depth: int) -> int:
    """Performance test: count leaf nodes to `depth` from current game state.

    Uses quiet push/pop for speed and to avoid emitting arcane events.
    """
    if depth <= 0:
        return 1
    moves = game.legal_moves(game.side_to_move)
    if depth == 1:
        return len(moves)
    total = 0
    for m in moves:
        game.push_quiet(m)
        total += perft(game, depth - 1)
        game.pop_quiet()
    return total


def perft_divide(game: Game, depth: int) -> Dict[str, int]:
    """Divide perft: nodes per root move."""
    out: Dict[str, int] = {}
    for m in game.legal_moves(game.side_to_move):
        game.push_quiet(m)
        out[move_to_uci(m)] = perft(game, depth - 1)
        game.pop_quiet()
    return out
