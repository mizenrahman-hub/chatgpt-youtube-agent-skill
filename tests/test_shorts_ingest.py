import json
import tempfile
import unittest
from pathlib import Path

from shorts_ingest import validate_job


class IngestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "source.mp4").write_bytes(b"test source")
        self.job = self.root / "job.json"
        self.save({"source": "source.mp4"})

    def save(self, data):
        self.job.write_text(json.dumps(data), encoding="utf-8")

    def test_valid_source(self):
        result = validate_job(self.job, self.root)
        self.assertTrue(result["valid"])
        self.assertFalse(result["publish"])

    def test_missing_source(self):
        self.save({"source": "missing.mp4"})
        with self.assertRaises(FileNotFoundError):
            validate_job(self.job, self.root)

    def test_parent_escape(self):
        self.save({"source": "../source.mp4"})
        with self.assertRaises((ValueError, FileNotFoundError)):
            validate_job(self.job, self.root)

    def test_invalid_extension(self):
        (self.root / "source.txt").write_text("data")
        self.save({"source": "source.txt"})
        with self.assertRaises(ValueError):
            validate_job(self.job, self.root)

    def test_empty_source(self):
        (self.root / "source.mp4").write_bytes(b"")
        with self.assertRaises(ValueError):
            validate_job(self.job, self.root)

    def test_bad_subtitles(self):
        self.save({"source": "source.mp4", "subtitles": "../secret.srt"})
        with self.assertRaises((ValueError, FileNotFoundError)):
            validate_job(self.job, self.root)

    def test_invalid_url(self):
        self.save({"source": "source.mp4", "long_video_url": "https://example.com/video"})
        with self.assertRaises(ValueError):
            validate_job(self.job, self.root)


if __name__ == "__main__":
    unittest.main()
