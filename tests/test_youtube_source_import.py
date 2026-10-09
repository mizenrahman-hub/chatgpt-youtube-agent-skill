import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from youtube_source_import import import_video


class ImportTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {}, clear=True):
            self.assertEqual(import_video(Path(d))["status"], "disabled")

    def test_rejects_bad_video_id_before_network(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {
            "SHORTS_IMPORT_ENABLED": "true", "SHORTS_IMPORT_VIDEO_ID": "../unsafe"
        }, clear=True):
            with self.assertRaises(ValueError):
                import_video(Path(d))

    def test_existing_source_pair_is_reused(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {
            "SHORTS_IMPORT_ENABLED": "true", "SHORTS_IMPORT_VIDEO_ID": "JUk8rJAuzCY"
        }, clear=True):
            (Path(d) / "JUk8rJAuzCY.mp4").write_bytes(b"video")
            (Path(d) / "JUk8rJAuzCY.srt").write_text("caption")
            self.assertEqual(import_video(Path(d))["status"], "ready")


if __name__ == "__main__":
    unittest.main()
