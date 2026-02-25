from __future__ import annotations

from typing import Iterable, List, Optional, Protocol, Sequence, Tuple, TYPE_CHECKING

from .definitions import CardinalDir

if TYPE_CHECKING:
    from ..core.game import Game
    from ..core.piece import Piece
    from ..core.moves import Move

class DecisionProvider(Protocol):
    def choose_block_path_dir(self, game: "Game", mover: "Piece") -> CardinalDir:
        ...

    def choose_double_kill_target(self, game: "Game", capturer: "Piece", candidates: Sequence["Piece"]) -> Optional["Piece"]:
        ...

    def choose_necromancer_resurrect(self, game: "Game", candidates: Sequence[Tuple["Piece", int]]) -> Optional[Tuple["Piece", int]]:
        ...

    def choose_redo_replay(self, game: "Game", defender_color, forbidden: "Move", legal: Sequence["Move"]) -> Optional["Move"]:
        ...

class DefaultDecisions:
    def choose_block_path_dir(self, game: "Game", mover: "Piece") -> CardinalDir:
        return CardinalDir.NORTH

    def choose_double_kill_target(self, game: "Game", capturer: "Piece", candidates: Sequence["Piece"]) -> Optional["Piece"]:
        return candidates[0] if candidates else None

    def choose_necromancer_resurrect(self, game: "Game", candidates: Sequence[Tuple["Piece", int]]) -> Optional[Tuple["Piece", int]]:
        return candidates[0] if candidates else None

    def choose_redo_replay(self, game: "Game", defender_color, forbidden: "Move", legal: Sequence["Move"]) -> Optional["Move"]:
        # choose any move that's not the same from/to/type/flags
        for m in legal:
            if (m.__class__ is forbidden.__class__ and m.from_sq == forbidden.from_sq and m.to_sq == forbidden.to_sq and getattr(m, "flags", ()) == getattr(forbidden, "flags", ())):
                continue
            return m
        return None
