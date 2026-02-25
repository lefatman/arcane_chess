import importlib.util
import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from arcane_interaction_chess.core import Game, setup_standard
from arcane_interaction_chess.core.moves import NormalMove
from arcane_interaction_chess.core.types import FILES, sq


def _sq(alg: str) -> int:
    file_idx = FILES.index(alg[0])
    rank_idx = int(alg[1]) - 1
    return sq(file_idx, rank_idx)


def _load_frontend_server_module():
    root = Path(__file__).resolve().parents[2]
    mod_path = root / "frontend" / "server.py"
    spec = importlib.util.spec_from_file_location("frontend_server", mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load frontend server module")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("frontend_server", module)
    spec.loader.exec_module(module)
    return module


class TestIllegalInputRejected(unittest.TestCase):
    def test_push_rejects_opposite_color_piece(self):
        g = Game()
        setup_standard(g)
        with self.assertRaisesRegex(ValueError, "Wrong side to move"):
            g.push(NormalMove(_sq("e7"), _sq("e6")))

    def test_push_checked_rejects_illegal_knight_and_king_moves(self):
        g = Game()
        setup_standard(g)
        with self.assertRaisesRegex(ValueError, "Illegal move"):
            g.push_checked(NormalMove(_sq("b1"), _sq("b4")))
        with self.assertRaisesRegex(ValueError, "Illegal move"):
            g.push_checked(NormalMove(_sq("e1"), _sq("e3")))

    def test_server_engine_rejects_malformed_and_mismatched_move_fields(self):
        server_module = _load_frontend_server_module()
        engine = server_module.ServerEngine.standard_demo_game()


        with self.assertRaisesRegex(ValueError, "Illegal move"):
            engine.apply({"kind": "normal", "from_alg": "e7", "to_alg": "e6"})

        with self.assertRaisesRegex(ValueError, "Illegal move"):
            engine.apply({"kind": "normal", "from_alg": "b1", "to_alg": "b4"})

        with self.assertRaisesRegex(ValueError, "Illegal move"):
            engine.apply({"kind": "promotion", "from_alg": "e2", "to_alg": "e4", "promote_to": "Queen"})

        with self.assertRaisesRegex(ValueError, "Illegal move"):
            engine.apply({"kind": "normal", "from_alg": "e2", "to_alg": "e4", "flags": ["bogus"]})

    def test_api_apply_returns_400_for_illegal_input(self):
        server_module = _load_frontend_server_module()
        server_module.STATE.engine = server_module.ServerEngine.standard_demo_game()
        server_module.STATE.pending = None
        server_module.STATE.pending_move = None

        httpd = server_module.ThreadingHTTPServer(("127.0.0.1", 0), server_module.Handler)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()

        try:
            url = f"http://127.0.0.1:{httpd.server_port}/api/apply"
            payload = json.dumps({"move": {"kind": "normal", "from_alg": "e7", "to_alg": "e6"}}).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with self.assertRaises(urllib.error.HTTPError) as exc:
                urllib.request.urlopen(req)
            self.assertEqual(exc.exception.code, 400)
        finally:
            httpd.shutdown()
            httpd.server_close()
            thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
