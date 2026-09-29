import tempfile
import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from urdf_forward_kinematics import UrdfKinematics


URDF = """<robot name="test">
<link name="base"/><link name="arm"/><link name="tool"/>
<joint name="turn" type="revolute">
  <parent link="base"/><child link="arm"/>
  <origin xyz="1 0 0" rpy="0 0 0"/><axis xyz="0 0 1"/>
</joint>
<joint name="tool_fixed" type="fixed">
  <parent link="arm"/><child link="tool"/>
  <origin xyz="1 0 0" rpy="0 0 0"/>
</joint>
</robot>"""


class UrdfForwardKinematicsTests(unittest.TestCase):
    def make_model(self):
        directory = tempfile.TemporaryDirectory()
        path = Path(directory.name) / "test.urdf"
        path.write_text(URDF, encoding="utf-8")
        return directory, UrdfKinematics.from_file(path)

    def test_revolute_then_fixed_chain(self):
        directory, model = self.make_model()
        try:
            transform = model.forward({"turn": np.pi / 2}, "base", "tool")
            np.testing.assert_allclose(transform[:3, 3], [1, 1, 0], atol=1e-10)
            np.testing.assert_allclose(
                transform[:3, :3], [[0, -1, 0], [1, 0, 0], [0, 0, 1]], atol=1e-10
            )
        finally:
            directory.cleanup()

    def test_requires_movable_joint_value(self):
        directory, model = self.make_model()
        try:
            with self.assertRaises(ValueError):
                model.forward({}, "base", "tool")
        finally:
            directory.cleanup()

    def test_rejects_unknown_target(self):
        directory, model = self.make_model()
        try:
            with self.assertRaises(ValueError):
                model.forward({"turn": 0.0}, "base", "missing")
        finally:
            directory.cleanup()


if __name__ == "__main__":
    unittest.main()
