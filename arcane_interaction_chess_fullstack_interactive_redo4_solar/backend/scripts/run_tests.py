#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
import unittest

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(str(BACKEND_DIR / "tests"))
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    raise SystemExit(0 if res.wasSuccessful() else 1)
