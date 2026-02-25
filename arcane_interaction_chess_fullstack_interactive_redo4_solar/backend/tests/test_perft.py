import unittest

from arcane_interaction_chess.fen import parse_fen, STARTPOS_FEN
from arcane_interaction_chess.core import Game, setup_standard, PositionTracker
from arcane_interaction_chess.perft import perft


class TestPerft(unittest.TestCase):
    def test_startpos(self):
        g = parse_fen(STARTPOS_FEN)
        PositionTracker().attach(g)
        self.assertEqual(perft(g, 1), 20)
        self.assertEqual(perft(g, 2), 400)
        self.assertEqual(perft(g, 3), 8902)

    def test_kiwipete(self):
        fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"
        g = parse_fen(fen)
        PositionTracker().attach(g)
        self.assertEqual(perft(g, 1), 48)
        self.assertEqual(perft(g, 2), 2039)
        self.assertEqual(perft(g, 3), 97862)


if __name__ == "__main__":
    unittest.main()
