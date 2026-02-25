from __future__ import annotations

from typing import Dict, Iterator, List, Optional

from .piece import Piece
from .types import Color, sq_name
from .pieces import King

class Board:
    def __init__(self) -> None:
        self._pieces: Dict[int, Piece] = {}

    def piece_at(self, s: int) -> Optional[Piece]:
        return self._pieces.get(s)

    def add_piece(self, p: Piece) -> None:
        if p.pos in self._pieces:
            raise ValueError(f"Square {sq_name(p.pos)} occupied")
        self._pieces[p.pos] = p

    def remove_piece(self, s: int) -> None:
        self._pieces.pop(s, None)

    def move_piece(self, from_sq: int, to_sq: int) -> None:
        p = self._pieces.pop(from_sq)
        p.pos = to_sq
        self._pieces[to_sq] = p

    def iter_pieces_of(self, color: Color) -> Iterator[Piece]:
        for square in tuple(self._pieces):
            piece = self._pieces.get(square)
            if piece is not None and piece.color is color:
                yield piece

    def pieces_of(self, color: Color) -> List[Piece]:
        return list(self.iter_pieces_of(color))

    def king_of(self, color: Color) -> King:
        for p in self._pieces.values():
            if p.color is color and isinstance(p, King):
                return p
        raise ValueError("King not found")
