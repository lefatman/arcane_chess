from __future__ import annotations

from typing import Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from .piece import Piece
    from .game import Game
    from .moves import Move

class Ability:
    """A capability a piece can have: movement, attacks, and reactive hooks."""

    def generate_moves(self, piece: "Piece", game: "Game") -> Iterable["Move"]:
        return ()

    def generate_attacks(self, piece: "Piece", game: "Game") -> Iterable[int]:
        return ()

    def on_event(self, piece: "Piece", game: "Game", event: object) -> None:
        return
