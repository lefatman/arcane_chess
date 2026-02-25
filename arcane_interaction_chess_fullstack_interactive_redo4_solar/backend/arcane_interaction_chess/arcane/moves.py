from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from ..core.moves import Move, Undo

if TYPE_CHECKING:
    from ..core.game import Game

@dataclass(frozen=True)
class RemoteCaptureMove(Move):
    origin_sq: int = -1  # adjacent ally square used as the virtual capture origin

    def apply(self, game: "Game") -> Undo:
        board = game.board
        mover = board.piece_at(self.from_sq)
        if mover is None:
            raise ValueError("No piece to remote-capture with")

        target = board.piece_at(self.to_sq)
        captured = None

        undo = Undo(prev_last_move=game.last_move, prev_side=game.side_to_move)
        undo.move = self
        undo.mover = mover
        undo.captured_piece = None

        # mark this piece as having moved (it's an action)
        undo.changed.append((mover, mover.pos, mover.has_moved))
        mover.has_moved = True

        if target is not None and target.color != mover.color:
            should_capture = True
            fn = getattr(game, "arcane_remote_capture_should_capture", None)
            if fn is not None:
                should_capture = bool(fn(mover, self.origin_sq, target))
            if should_capture:
                captured = target
                undo.captured_piece = captured
                undo.captured.append((captured, captured.pos, captured.has_moved))
                board.remove_piece(captured.pos)

        game.last_move = self
        game.side_to_move = game.side_to_move.opponent()
        return undo
