from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, Tuple, TYPE_CHECKING

from .ability import Ability
from .types import Color

_UID = 1

def _next_uid() -> int:
    global _UID
    uid = _UID
    _UID += 1
    return uid

@dataclass
class Piece:
    color: Color
    pos: int
    symbol: str
    abilities: Tuple[Ability, ...]
    has_moved: bool = False
    uid: int = field(default_factory=_next_uid)
    meta: Dict[str, object] = field(default_factory=dict)

    def pseudo_legal_moves(self, game: "Game") -> Iterable["Move"]:
        for ab in self.abilities:
            yield from ab.generate_moves(self, game)

    def attacks(self, game: "Game") -> Iterable[int]:
        for ab in self.abilities:
            yield from ab.generate_attacks(self, game)

    def on_event(self, game: "Game", event: object) -> None:
        for ab in self.abilities:
            ab.on_event(self, game, event)

# typing-only
if TYPE_CHECKING:
    from .game import Game
    from .moves import Move
