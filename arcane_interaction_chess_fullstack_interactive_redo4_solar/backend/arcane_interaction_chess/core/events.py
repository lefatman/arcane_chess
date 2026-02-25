from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .moves import Move
    from .piece import Piece

@dataclass(frozen=True)
class MoveWillApply:
    move: "Move"
    mover: "Piece"

@dataclass(frozen=True)
class MoveApplied:
    move: "Move"
    mover: "Piece"
    captured: Optional["Piece"]

@dataclass(frozen=True)
class MoveUndone:
    move: "Move"
    mover: "Piece"
    captured: Optional["Piece"]
