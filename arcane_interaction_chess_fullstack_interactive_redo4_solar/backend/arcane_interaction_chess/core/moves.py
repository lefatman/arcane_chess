from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple, Type, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .game import Game
    from .piece import Piece


ChangedPieceState = Tuple["Piece", int, bool, int]

@dataclass(frozen=True)
class Move:
    from_sq: int
    to_sq: int
    flags: Tuple[str, ...] = ()

    def apply(self, game: "Game") -> "Undo":
        raise NotImplementedError

@dataclass(frozen=True)
class NormalMove(Move):
    def apply(self, game: "Game") -> "Undo":
        board = game.board
        moved = board.piece_at(self.from_sq)
        if moved is None:
            raise ValueError("No piece to move")

        captured = board.piece_at(self.to_sq)

        undo = Undo(prev_last_move=game.last_move, prev_side=game.side_to_move)
        undo.move = self
        undo.mover = moved
        undo.captured_piece = captured

        undo.changed.append((moved, moved.pos, moved.has_moved, self.to_sq))
        if captured is not None:
            undo.captured.append((captured, captured.pos, captured.has_moved))
            board.remove_piece(captured.pos)

        board.move_piece(self.from_sq, self.to_sq)
        moved.has_moved = True

        game.last_move = self
        game.side_to_move = game.side_to_move.opponent()
        return undo

@dataclass(frozen=True)
class EnPassantMove(Move):
    captured_sq: int = -1

    def apply(self, game: "Game") -> "Undo":
        board = game.board
        moved = board.piece_at(self.from_sq)
        captured = board.piece_at(self.captured_sq)
        if moved is None or captured is None:
            raise ValueError("Invalid en passant state")

        undo = Undo(prev_last_move=game.last_move, prev_side=game.side_to_move)
        undo.move = self
        undo.mover = moved
        undo.captured_piece = captured

        undo.changed.append((moved, moved.pos, moved.has_moved, self.to_sq))
        undo.captured.append((captured, captured.pos, captured.has_moved))

        board.remove_piece(self.captured_sq)
        board.move_piece(self.from_sq, self.to_sq)
        moved.has_moved = True

        game.last_move = self
        game.side_to_move = game.side_to_move.opponent()
        return undo

@dataclass(frozen=True)
class CastleMove(Move):
    rook_from: int = -1
    rook_to: int = -1

    def apply(self, game: "Game") -> "Undo":
        board = game.board
        king = board.piece_at(self.from_sq)
        rook = board.piece_at(self.rook_from)
        if king is None or rook is None:
            raise ValueError("Invalid castling state")

        undo = Undo(prev_last_move=game.last_move, prev_side=game.side_to_move)
        undo.move = self
        undo.mover = king
        undo.captured_piece = None

        undo.changed.append((king, king.pos, king.has_moved, self.to_sq))
        undo.changed.append((rook, rook.pos, rook.has_moved, self.rook_to))

        board.move_piece(self.from_sq, self.to_sq)
        board.move_piece(self.rook_from, self.rook_to)

        king.has_moved = True
        rook.has_moved = True

        game.last_move = self
        game.side_to_move = game.side_to_move.opponent()
        return undo

@dataclass(frozen=True)
class PromotionMove(Move):
    promote_to: Type["Piece"] = None  # type: ignore[assignment]

    def apply(self, game: "Game") -> "Undo":
        board = game.board
        pawn = board.piece_at(self.from_sq)
        if pawn is None:
            raise ValueError("No pawn to promote")

        captured = board.piece_at(self.to_sq)

        undo = Undo(prev_last_move=game.last_move, prev_side=game.side_to_move)
        undo.move = self
        # For promotion, the *move actor* is still the pawn (pre-promotion).
        # This keeps on-capture rank comparisons and pawn-typed triggers coherent.
        # The promoted piece is tracked in undo.added and can be inspected via
        # board.piece_at(to_sq) by downstream systems when they need the post-
        # promotion piece (e.g., for Poisoned Dagger removing the actual capturer).
        undo.mover = pawn
        undo.captured_piece = captured

        undo.removed.append((pawn, pawn.pos, pawn.has_moved))
        board.remove_piece(self.from_sq)

        if captured is not None:
            undo.captured.append((captured, captured.pos, captured.has_moved))
            board.remove_piece(captured.pos)

        promoted = self.promote_to(pawn.color, self.to_sq)  # type: ignore[misc]
        promoted.has_moved = True
        board.add_piece(promoted)
        undo.added.append(promoted)

        game.last_move = self
        game.side_to_move = game.side_to_move.opponent()
        return undo

@dataclass
class Undo:
    prev_last_move: Optional[Move]
    prev_side: "Color"

    move: Optional[Move] = None
    mover: Optional["Piece"] = None
    captured_piece: Optional["Piece"] = None

    changed: List[ChangedPieceState] = None
    captured: List[Tuple["Piece", int, bool]] = None
    removed: List[Tuple["Piece", int, bool]] = None
    added: List["Piece"] = None

    # snapshots for per-piece meta dict
    piece_meta_snapshots: List[Tuple["Piece", dict]] = None

    # generic extensibility bucket (arcane can store snapshots here)
    extras: dict = None

    def __post_init__(self) -> None:
        self.changed = [] if self.changed is None else self.changed
        self.captured = [] if self.captured is None else self.captured
        self.removed = [] if self.removed is None else self.removed
        self.added = [] if self.added is None else self.added
        self.piece_meta_snapshots = [] if self.piece_meta_snapshots is None else self.piece_meta_snapshots
        self.extras = {} if self.extras is None else self.extras

    def snapshot_piece_meta(self, p: "Piece") -> None:
        # snapshot once per piece per ply
        for existing, _ in self.piece_meta_snapshots:
            if existing is p:
                return
        self.piece_meta_snapshots.append((p, dict(p.meta)))
