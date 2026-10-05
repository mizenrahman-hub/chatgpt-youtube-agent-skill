import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from shorts_pipeline import candidates, clipped_srt, run_job, run_queue


class ShortsTests(unittest.TestCase):
    def test_subtitles_rebased_and_clipped(self):
        text = clipped_srt([(8, 12, "ilk"), (14, 19, "son"), (20, 22, "dış")], 10, 16)
        self.assertIn("00:00:00,000 --> 00:00:02,000", text)
        self.assertIn("00:00:04,000 --> 00:00:06,000", text)
        self.assertNotIn("dış", text)

    def test_candidate_selection_deduplicates_and_does_not_invent(self):
        clips = candidates([(10, 12, "kim var mağara"), (12, 15, "ses"), (80, 82, "korktum")], 120)
        self.assertEqual(len(clips), 2)
        self.assertEqual(candidates([(0, 2, "merhaba")], 120), [])

    def test_invalid_ranges_rejected_before_render(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            (root / "source.mp4").touch()
            for start, end in [(-1, 20), (0, 61), (90, 120), (float("nan"), 20)]:
                job = root / "job.json"
                job.write_text(json.dumps({"source": "source.mp4", "clips": [{"start": start, "end": end}]}))
                with patch("shorts_pipeline.probe", return_value=100), self.assertRaises(ValueError):
                    run_job(job, root / "out", True)

    @unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg required")
    def test_real_render_audio_captions_and_completed_queue_skip(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            inbox = root / "inbox"
            inbox.mkdir()
            source = inbox / "source.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=5:d=16",
                            "-f", "lavfi", "-i", "sine=frequency=440:duration=16", "-c:v", "libx264",
                            "-c:a", "aac", "-shortest", str(source)], check=True)
            (inbox / "captions.srt").write_text("1\n00:00:02,000 --> 00:00:04,000\nTürkçe altyazı\n", encoding="utf-8")
            job = inbox / "job.json"
            job.write_text(json.dumps({"source": "source.mp4", "subtitles": "captions.srt",
                                       "clips": [{"start": 0, "end": 15, "hook": "Kim var?"}]}))
            out = root / "out"
            report = run_job(job, out, True)
            self.assertEqual(report["status"], "awaiting_review")
            video = next(out.glob("*/short-1.mp4"))
            data = json.loads(subprocess.check_output(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)]))
            stream = next(s for s in data["streams"] if s["codec_type"] == "video")
            self.assertEqual((stream["width"], stream["height"]), (1080, 1920))
            self.assertTrue(any(s["codec_type"] == "audio" for s in data["streams"]))
            self.assertAlmostEqual(float(data["format"]["duration"]), 15, delta=0.3)
            with patch.dict("os.environ", {"SHORTS_INBOX": str(inbox), "SHORTS_OUTPUT": str(out)}):
                self.assertIsNone(run_queue())
            self.assertTrue(source.is_file())


if __name__ == "__main__":
    unittest.main()
