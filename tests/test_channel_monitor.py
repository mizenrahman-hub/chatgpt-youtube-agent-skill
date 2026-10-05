import unittest

from channel_monitor import scan_channel


class Request:
    def __init__(self, payload):
        self.payload = payload
    def execute(self):
        return self.payload


class Resource:
    def __init__(self, payload):
        self.payload = payload
    def list(self, **kwargs):
        return Request(self.payload)


class YouTube:
    def channels(self):
        return Resource({"items":[{
            "id":"channel-1",
            "snippet":{"title":"Ramy Yollarda"},
            "contentDetails":{"relatedPlaylists":{"uploads":"uploads-1"}},
            "statistics":{"subscriberCount":"18000","viewCount":"100000","videoCount":"20"},
        }]})
    def playlistItems(self):
        return Resource({"items":[{"contentDetails":{"videoId":"video-1"}}]})
    def videos(self):
        return Resource({"items":[{
            "id":"video-1",
            "snippet":{"title":"Test","publishedAt":"2026-10-05T00:00:00Z"},
            "contentDetails":{"duration":"PT10M"},
            "statistics":{"viewCount":"100","likeCount":"10","commentCount":"2"},
        }]})


class ChannelMonitorTests(unittest.TestCase):
    def test_scan_is_read_only_summary(self):
        result = scan_channel(YouTube(), max_results=10)
        self.assertEqual(result["channel_id"], "channel-1")
        self.assertEqual(result["recent_videos"][0]["views"], 100)
        self.assertEqual(result["recent_videos"][0]["title"], "Test")

    def test_max_results_guard(self):
        with self.assertRaises(ValueError):
            scan_channel(YouTube(), max_results=51)


if __name__ == "__main__":
    unittest.main()
