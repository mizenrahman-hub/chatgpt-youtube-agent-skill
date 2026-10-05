import os
import unittest
from unittest.mock import MagicMock, patch

import worker


class WorkerConfigTests(unittest.TestCase):
    def test_default_max_results_is_ten(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(worker._positive_int("YOUTUBE_SCAN_MAX_RESULTS", 10), 10)

    def test_invalid_integer_is_rejected(self):
        with patch.dict(os.environ, {"YOUTUBE_SCAN_MAX_RESULTS": "not-a-number"}, clear=True):
            with self.assertRaises(SystemExit):
                worker._positive_int("YOUTUBE_SCAN_MAX_RESULTS", 10)

    def test_run_once_scans_once(self):
        youtube = MagicMock()
        snapshot = {"channel_id": "channel-1", "recent_videos": [{}, {}]}
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(worker, "build_youtube_client", return_value=youtube), \
             patch.object(worker, "verify_channel_access") as verify, \
             patch.object(worker, "scan_channel", return_value=snapshot) as scan:
            self.assertEqual(worker.run_once(), snapshot)
            verify.assert_called_once_with(youtube)
            scan.assert_called_once_with(youtube, max_results=10)


if __name__ == "__main__":
    unittest.main()
