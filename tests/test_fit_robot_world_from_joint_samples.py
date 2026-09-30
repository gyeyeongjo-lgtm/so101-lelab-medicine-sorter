import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from scripts.fit_robot_world_from_joint_samples import load_reviewed_pairs


class FakeKinematics:
    def forward(self, joints, root, target):
        self.asserted = (root, target)
        return np.eye(4)


def fixture(jaws=None):
    jaws = jaws or [0.08] * 4
    return {
        "robot_enabled": False,
        "motion_authorized": False,
        "pairs": [
            {
                "name": f"P{index}",
                "joint_sample": {
                    "source": "LeLab /ws/joint-data",
                    "serial_access": False,
                    "samples": 15,
                    "max_std_rad": 0.0,
                    "joints_mean": {
                        "Rotation": 0.0,
                        "Pitch": 0.0,
                        "Elbow": 0.0,
                        "Wrist_Pitch": 0.0,
                        "Wrist_Roll": 0.0,
                        "Jaw": jaw,
                    },
                },
            }
            for index, jaw in enumerate(jaws, start=1)
        ],
    }


class JointSampleFitInputTests(unittest.TestCase):
    def read(self, document):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "pairs.json"
            path.write_text(json.dumps(document), encoding="utf-8")
            with patch(
                "scripts.fit_robot_world_from_joint_samples.UrdfKinematics.from_file",
                return_value=FakeKinematics(),
            ):
                return load_reviewed_pairs(path, Path(directory) / "unused.urdf")

    def test_derives_fk_only_from_reviewed_broadcast(self):
        result, jaws = self.read(fixture())
        self.assertEqual(len(jaws), 4)
        self.assertEqual(result["pairs"][0]["gripper_link_origin_mm"], [0.0, 0.0, 0.0])
        self.assertEqual(result["pairs"][0]["gripper_link_rotation"], np.eye(3).tolist())

    def test_rejects_motion_enabled_source(self):
        document = fixture()
        document["robot_enabled"] = True
        with self.assertRaisesRegex(ValueError, "block robot motion"):
            self.read(document)

    def test_rejects_unstable_or_nonbroadcast_sample(self):
        document = fixture()
        document["pairs"][0]["joint_sample"]["max_std_rad"] = 0.02
        with self.assertRaisesRegex(ValueError, "unstable sample"):
            self.read(document)
        document = fixture()
        document["pairs"][0]["joint_sample"]["source"] = "another serial reader"
        with self.assertRaisesRegex(ValueError, "missing LeLab broadcast"):
            self.read(document)

    def test_rejects_jaw_change(self):
        with self.assertRaisesRegex(ValueError, "Jaw changed too much"):
            self.read(fixture([0.08, 0.08, 0.08, 0.12]))


if __name__ == "__main__":
    unittest.main()
