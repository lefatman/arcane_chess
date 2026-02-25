from __future__ import annotations

from .types import Color, sq
from .pieces import King, Queen, Rook, Bishop, Knight, Pawn

def setup_standard(game) -> None:
    # White
    game.board.add_piece(Rook(Color.WHITE, sq(0, 0)))
    game.board.add_piece(Knight(Color.WHITE, sq(1, 0)))
    game.board.add_piece(Bishop(Color.WHITE, sq(2, 0)))
    game.board.add_piece(Queen(Color.WHITE, sq(3, 0)))
    game.board.add_piece(King(Color.WHITE, sq(4, 0)))
    game.board.add_piece(Bishop(Color.WHITE, sq(5, 0)))
    game.board.add_piece(Knight(Color.WHITE, sq(6, 0)))
    game.board.add_piece(Rook(Color.WHITE, sq(7, 0)))
    for f in range(8):
        game.board.add_piece(Pawn(Color.WHITE, sq(f, 1)))

    # Black
    game.board.add_piece(Rook(Color.BLACK, sq(0, 7)))
    game.board.add_piece(Knight(Color.BLACK, sq(1, 7)))
    game.board.add_piece(Bishop(Color.BLACK, sq(2, 7)))
    game.board.add_piece(Queen(Color.BLACK, sq(3, 7)))
    game.board.add_piece(King(Color.BLACK, sq(4, 7)))
    game.board.add_piece(Bishop(Color.BLACK, sq(5, 7)))
    game.board.add_piece(Knight(Color.BLACK, sq(6, 7)))
    game.board.add_piece(Rook(Color.BLACK, sq(7, 7)))
    for f in range(8):
        game.board.add_piece(Pawn(Color.BLACK, sq(f, 6)))

def ascii_board(game) -> str:
    rows = []
    for r in range(7, -1, -1):
        row = []
        for f in range(8):
            p = game.board.piece_at(sq(f, r))
            row.append(p.symbol if p else ".")
        rows.append(" ".join(row))
    return "\n".join(rows)
