from __future__ import annotations

from typing import Iterable, Protocol, TYPE_CHECKING

from .types import Color

if TYPE_CHECKING:
    from .moves import Move
    from .game import Game

class Rule(Protocol):
    def apply(self, game: "Game", color: Color, moves: Iterable["Move"]) -> Iterable["Move"]:
        ...

class KingSafetyRule:
    """Reject any move that leaves your own king in check. Uses quiet simulation."""
    def apply(self, game: "Game", color: Color, moves: Iterable["Move"]) -> Iterable["Move"]:
        for m in moves:
            game.push_quiet(m)
            illegal = game.in_check(color)
            game.pop_quiet()
            if not illegal:
                yield m
