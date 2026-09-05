from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "preflight.py"
SPEC = importlib.util.spec_from_file_location("preflight", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PreflightTest(unittest.TestCase):
    def test_missing_devices_block_readiness(self):
        with tempfile.TemporaryDirectory() as directory:
            report = MODULE.validate(
                {
                    "leader_port": "/missing/leader",
                    "follower_port": "/missing/follower",
                    "leader_config": "leader.json",
                    "follower_config": "follower.json",
                    "cameras": [],
                },
                Path(directory),
            )
        self.assertFalse(report["ready"])
        self.assertEqual(report["summary"], {"pass": 0, "fail": 4, "blocked": 1})


if __name__ == "__main__":
    unittest.main()
