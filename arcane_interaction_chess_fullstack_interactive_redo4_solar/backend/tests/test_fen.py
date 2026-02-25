import unittest

from arcane_interaction_chess.fen import parse_fen, game_to_fen, STARTPOS_FEN
from arcane_interaction_chess.core import PositionTracker


class TestFEN(unittest.TestCase):
    def test_roundtrip_startpos(self):
        g = parse_fen(STARTPOS_FEN)
        PositionTracker().attach(g)
        self.assertEqual(game_to_fen(g), STARTPOS_FEN)

    def test_roundtrip_kiwipete(self):
        fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        g = parse_fen(fen)
        PositionTracker().attach(g)
        self.assertEqual(game_to_fen(g), fen)

    def test_fen_invalid_cases(self):
        fen_invalid_cases = (
            "4k3/8/8/8/8/8/8/8 w - - 0 1",  # missing white king
            "4k3/8/8/8/8/8/8/4K2K w - - 0 1",  # extra white king
            "4k3/8/8/8/8/8/8/4K3 w K - 0 1",  # K without rook h1
            "4k3/8/8/8/8/8/8/4K3 w Q - 0 1",  # Q without rook a1
            "4k3/8/8/8/8/8/8/4K2R w k - 0 1",  # k without black king+rook on home squares
            "4k3/8/8/8/8/8/8/4K3 w q - 0 1",  # q without black rook a8
            "4k3/8/8/8/8/8/8/4K3 w KK - 0 1",  # duplicate castling flag
            "4k3/8/8/8/8/8/8/4K3 w A - 0 1",  # invalid castling flag
            "4k3/8/8/8/8/8/8/4K3 w - e3 0 1",  # white to move must use rank 6 EP square
            "4k3/8/8/8/8/8/8/4K3 b - e6 0 1",  # black to move must use rank 3 EP square
            "4k3/8/8/8/8/8/8/4K3 w - e6 0 1",  # no pawn on expected destination square
            "4k3/8/8/8/4p3/8/4P3/4K3 w - e6 0 1",  # origin square must be empty after push
        )

        for fen in fen_invalid_cases:
            with self.subTest(fen=fen):
                with self.assertRaises(ValueError):
                    parse_fen(fen)


if __name__ == "__main__":
    unittest.main()
