from __future__ import annotations

from enum import Enum

class Color(Enum):
    WHITE = 1
    BLACK = -1

    def opponent(self) -> "Color":
        return Color.BLACK if self is Color.WHITE else Color.WHITE

FILES = "abcdefgh"

def sq(file: int, rank: int) -> int:
    return rank * 8 + file

def file_of(s: int) -> int:
    return s % 8

def rank_of(s: int) -> int:
    return s // 8

def in_bounds(file: int, rank: int) -> bool:
    return 0 <= file < 8 and 0 <= rank < 8

def sq_name(s: int) -> str:
    return f"{FILES[file_of(s)]}{rank_of(s) + 1}"
