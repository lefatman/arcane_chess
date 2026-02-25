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


if __name__ == "__main__":
    unittest.main()
