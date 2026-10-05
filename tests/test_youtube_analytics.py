import unittest
from datetime import date

from youtube_analytics import query_channel_analytics


class Request:
    def __init__(self, payload):
        self.payload = payload
    def execute(self):
        return self.payload


class Reports:
    def __init__(self):
        self.calls = []
    def query(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("dimensions") == "video":
            return Request({
                "columnHeaders": [{"name":"video"},{"name":"views"}],
                "rows": [["abc", 123]],
            })
        return Request({
            "columnHeaders": [{"name":"views"},{"name":"estimatedMinutesWatched"}],
            "rows": [[456, 789]],
        })


class Analytics:
    def __init__(self):
        self.resource = Reports()
    def reports(self):
        return self.resource


class AnalyticsTests(unittest.TestCase):
    def test_queries_channel_and_video_metrics(self):
        api = Analytics()
        result = query_channel_analytics(api, end_date=date(2026, 10, 4), days=28)
        self.assertEqual(result["start_date"], "2026-09-07")
        self.assertEqual(result["end_date"], "2026-10-04")
        self.assertEqual(result["channel"][0]["views"], 456)
        self.assertEqual(result["videos"][0]["video"], "abc")
        self.assertEqual(len(api.resource.calls), 2)
        self.assertTrue(all(call["ids"] == "channel==MINE" for call in api.resource.calls))

    def test_rejects_invalid_window(self):
        with self.assertRaises(ValueError):
            query_channel_analytics(Analytics(), days=0)


if __name__ == "__main__":
    unittest.main()
