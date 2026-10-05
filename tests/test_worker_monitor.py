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

    def test_analytics_is_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(worker._enabled("YOUTUBE_ANALYTICS_ENABLED"))

    def test_run_once_scans_once_without_analytics_by_default(self):
        youtube = MagicMock()
        snapshot = {"channel_id": "channel-1", "recent_videos": [{}, {}]}
        with patch.dict(os.environ, {}, clear=True), \
             patch.object(worker, "build_youtube_client", return_value=youtube), \
             patch.object(worker, "verify_channel_access") as verify, \
             patch.object(worker, "scan_channel", return_value=snapshot) as scan, \
             patch.object(worker, "build_youtube_analytics_client") as analytics_client:
            self.assertEqual(worker.run_once(), snapshot)
            verify.assert_called_once_with(youtube)
            scan.assert_called_once_with(youtube, max_results=10)
            analytics_client.assert_not_called()

    def test_run_once_queries_analytics_when_enabled(self):
        youtube = MagicMock()
        analytics = MagicMock()
        snapshot = {"channel_id": "channel-1", "recent_videos": []}
        report = {"channel": [{"views": 1}], "videos": []}
        with patch.dict(os.environ, {"YOUTUBE_ANALYTICS_ENABLED": "true"}, clear=True), \
             patch.object(worker, "build_youtube_client", return_value=youtube), \
             patch.object(worker, "verify_channel_access"), \
             patch.object(worker, "scan_channel", return_value=snapshot), \
             patch.object(worker, "build_youtube_analytics_client", return_value=analytics), \
             patch.object(worker, "query_channel_analytics", return_value=report) as query:
            worker.run_once()
            query.assert_called_once_with(analytics, max_results=10)


if __name__ == "__main__":
    unittest.main()
