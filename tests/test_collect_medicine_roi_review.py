import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from collect_medicine_roi_review import iter_mjpeg_jpegs, max_marker_shift, validate_args


class CollectorTests(unittest.TestCase):
    def test_reads_bounded_mjpeg_parts(self):
        stream = io.BytesIO(
            b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: 3\r\n\r\nabc\r\n"
            b"--frame\r\nContent-Length: 2\r\n\r\nde\r\n"
        )
        self.assertEqual(list(iter_mjpeg_jpegs(stream)), [b"abc", b"de"])

    def test_rejects_large_frame(self):
        stream = io.BytesIO(b"--frame\r\nContent-Length: 5000001\r\n\r\n")
        with self.assertRaises(ValueError):
            list(iter_mjpeg_jpegs(stream))

    def test_reference_shift(self):
        base = {marker_id: (float(marker_id), 0.0) for marker_id in range(4)}
        moved = dict(base)
        moved[2] = (base[2][0] + 3.0, 4.0)
        self.assertEqual(max_marker_shift(moved, base), 5.0)

    def test_output_must_be_new_and_thresholds_ordered(self):
        args = SimpleNamespace(
            crop_320=(128, 85, 215, 140), seconds=10, max_samples=5,
            sample_every_s=0.5, min_save_interval_s=2, stable_frames=3,
            stable_diff=2, novel_diff=3, max_marker_shift_px=5,
            output=Path("/a/path/that/does/not/exist"),
        )
        validate_args(args)
        args.novel_diff = 1
        with self.assertRaises(ValueError):
            validate_args(args)


if __name__ == "__main__":
    unittest.main()
