from __future__ import annotations

from .piece import Piece
from .types import Color
from .abilities import StepAbility, SlideAbility, PawnAbility, CastleAbility, KING8, ORTH, DIAG, KNIGHT_DELTAS

class King(Piece):
    def __init__(self, color: Color, pos: int) -> None:
        super().__init__(color, pos, "K" if color is Color.WHITE else "k",
                         (StepAbility(KING8), CastleAbility()))

class Queen(Piece):
    def __init__(self, color: Color, pos: int) -> None:
        super().__init__(color, pos, "Q" if color is Color.WHITE else "q",
                         (SlideAbility(KING8),))

class Rook(Piece):
    def __init__(self, color: Color, pos: int) -> None:
        super().__init__(color, pos, "R" if color is Color.WHITE else "r",
                         (SlideAbility(ORTH),))

class Bishop(Piece):
    def __init__(self, color: Color, pos: int) -> None:
        super().__init__(color, pos, "B" if color is Color.WHITE else "b",
                         (SlideAbility(DIAG),))

class Knight(Piece):
    def __init__(self, color: Color, pos: int) -> None:
        super().__init__(color, pos, "N" if color is Color.WHITE else "n",
                         (StepAbility(KNIGHT_DELTAS),))

class Pawn(Piece):
    def __init__(self, color: Color, pos: int) -> None:
        super().__init__(color, pos, "P" if color is Color.WHITE else "p",
                         (PawnAbility(),))
