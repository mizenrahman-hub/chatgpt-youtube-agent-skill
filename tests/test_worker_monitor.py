import os
import unittest
from unittest.mock import patch

import worker


class WorkerConfigTests(unittest.TestCase):
    def test_default_scan_interval_is_six_hours(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(worker._positive_int("YOUTUBE_SCAN_INTERVAL_SECONDS", 21600, 300), 21600)

    def test_scan_interval_rejects_less_than_five_minutes(self):
        with patch.dict(os.environ, {"YOUTUBE_SCAN_INTERVAL_SECONDS": "299"}, clear=True):
            with self.assertRaises(SystemExit):
                worker._positive_int("YOUTUBE_SCAN_INTERVAL_SECONDS", 21600, 300)

    def test_invalid_integer_is_rejected(self):
        with patch.dict(os.environ, {"PORT": "not-a-number"}, clear=True):
            with self.assertRaises(SystemExit):
                worker._positive_int("PORT", 8080)


if __name__ == "__main__":
    unittest.main()
