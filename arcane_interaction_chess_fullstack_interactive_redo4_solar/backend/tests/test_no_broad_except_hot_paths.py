from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
HOT_PATHS = [
    ROOT / "frontend" / "server.py",
    ROOT / "backend" / "arcane_interaction_chess" / "api" / "serde.py",
]
ALLOWED_PATTERNS = {
    "except Exception:\n            LOGGER.exception(\"api_get_unhandled\"",
    "except Exception:\n            LOGGER.exception(\"json_read_unhandled\"",
    "except Exception:\n            LOGGER.exception(\"api_post_unhandled\"",
}


class TestNoBroadExceptHotPaths(unittest.TestCase):
    def test_no_new_bare_broad_catches_in_hot_paths(self):
        violations = []
        for path in HOT_PATHS:
            content = path.read_text(encoding="utf-8")
            idx = 0
            while True:
                idx = content.find("except Exception:", idx)
                if idx < 0:
                    break
                segment = content[idx: idx + 96]
                if not any(segment.startswith(allowed) for allowed in ALLOWED_PATTERNS):
                    line = content.count("\n", 0, idx) + 1
                    violations.append(f"{path.relative_to(ROOT)}:{line}")
                idx += 1
        self.assertEqual(
            violations,
            [],
            msg="Broad except guard failed for hot paths: " + ", ".join(violations),
        )


if __name__ == "__main__":
    unittest.main()
