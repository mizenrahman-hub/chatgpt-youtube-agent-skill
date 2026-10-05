import os
import unittest
from unittest.mock import MagicMock

from safe_youtube_write import (
    MetadataProposal,
    SafetyError,
    apply_metadata_update,
)


class SafeWriteTests(unittest.TestCase):
    def setUp(self):
        self.proposal = MetadataProposal(
            video_id="M-laymnUCfQ",
            title="Yeni başlık",
            description="Yeni açıklama",
            tags=("Antalya", "gezi"),
            category_id="22",
        )
        self.youtube = MagicMock()
        self.youtube.videos.return_value.list.return_value.execute.return_value = {
            "items": [{"snippet": {"title": "Eski", "description": "Eski açıklama", "categoryId": "22"}}]
        }
        self.youtube.videos.return_value.update.return_value.execute.return_value = {"id": "M-laymnUCfQ"}
        os.environ.pop("YOUTUBE_WRITE_ENABLED", None)
        os.environ.pop("YOUTUBE_ALLOWED_VIDEO_ID", None)

    def tearDown(self):
        os.environ.pop("YOUTUBE_WRITE_ENABLED", None)
        os.environ.pop("YOUTUBE_ALLOWED_VIDEO_ID", None)

    def test_writes_are_off_by_default(self):
        with self.assertRaisesRegex(SafetyError, "disabled"):
            apply_metadata_update(self.youtube, self.proposal, approval_code=self.proposal.approval_code())
        self.youtube.videos.return_value.update.assert_not_called()

    def test_wrong_video_is_blocked(self):
        os.environ["YOUTUBE_WRITE_ENABLED"] = "true"
        os.environ["YOUTUBE_ALLOWED_VIDEO_ID"] = "different-video"
        with self.assertRaisesRegex(SafetyError, "allowlist"):
            apply_metadata_update(self.youtube, self.proposal, approval_code=self.proposal.approval_code())
        self.youtube.videos.return_value.update.assert_not_called()

    def test_changed_preview_invalidates_approval(self):
        os.environ["YOUTUBE_WRITE_ENABLED"] = "true"
        os.environ["YOUTUBE_ALLOWED_VIDEO_ID"] = self.proposal.video_id
        with self.assertRaisesRegex(SafetyError, "Approval"):
            apply_metadata_update(self.youtube, self.proposal, approval_code="stale-code")
        self.youtube.videos.return_value.update.assert_not_called()

    def test_only_snippet_update_runs_after_approval(self):
        os.environ["YOUTUBE_WRITE_ENABLED"] = "true"
        os.environ["YOUTUBE_ALLOWED_VIDEO_ID"] = self.proposal.video_id
        result = apply_metadata_update(
            self.youtube,
            self.proposal,
            approval_code=self.proposal.approval_code(),
        )
        self.youtube.videos.return_value.update.assert_called_once()
        body = self.youtube.videos.return_value.update.call_args.kwargs["body"]
        self.assertEqual(body["id"], self.proposal.video_id)
        self.assertEqual(body["snippet"]["title"], "Yeni başlık")
        self.assertEqual(result["backup"]["title"], "Eski")


if __name__ == "__main__":
    unittest.main()
