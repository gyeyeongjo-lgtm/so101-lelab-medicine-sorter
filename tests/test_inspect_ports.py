from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "inspect_ports.py"
SPEC = importlib.util.spec_from_file_location("inspect_ports", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InspectPortsTest(unittest.TestCase):
    def test_missing_path_is_reported(self):
        record = MODULE.inspect_path("/definitely/missing/so101-port", {})
        self.assertFalse(record["exists"])
        self.assertFalse(record["is_character_device"])
        self.assertIn("FileNotFoundError", record["error"])

    def test_two_aliases_share_one_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.write_text("not a serial device", encoding="utf-8")
            first = root / "leader"
            second = root / "follower"
            first.symlink_to(target)
            second.symlink_to(target)
            records = [MODULE.inspect_path(str(path), {}) for path in (first, second)]
            groups = MODULE.identity_groups(records)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["alias_count"], 2)
        self.assertEqual(groups[0]["identity"][1], "not-character-device")


if __name__ == "__main__":
    unittest.main()
