import unittest
from unittest.mock import MagicMock, patch

from youtube_oauth import (
    OAuthConfigurationError,
    YOUTUBE_SCOPE,
    build_youtube_client,
    verify_channel_access,
)


class YouTubeOAuthTests(unittest.TestCase):
    def setUp(self):
        self.environment = {
            "YOUTUBE_CLIENT_ID": "client-id",
            "YOUTUBE_CLIENT_SECRET": "client-secret",
            "YOUTUBE_REFRESH_TOKEN": "refresh-token",
        }

    def test_missing_variable_is_rejected_without_exposing_values(self):
        environment = dict(self.environment)
        del environment["YOUTUBE_CLIENT_SECRET"]
        with self.assertRaisesRegex(OAuthConfigurationError, "YOUTUBE_CLIENT_SECRET"):
            build_youtube_client(environment)

    @patch("youtube_oauth.build")
    @patch("youtube_oauth.Request")
    @patch("youtube_oauth.Credentials")
    def test_client_uses_expected_oauth_configuration(
        self, credentials_class, request_class, build
    ):
        credentials = credentials_class.return_value
        expected_client = build.return_value

        result = build_youtube_client(self.environment)

        credentials_class.assert_called_once_with(
            token=None,
            refresh_token="refresh-token",
            token_uri="https://oauth2.googleapis.com/token",
            client_id="client-id",
            client_secret="client-secret",
            scopes=[YOUTUBE_SCOPE],
        )
        credentials.refresh.assert_called_once_with(request_class.return_value)
        build.assert_called_once_with(
            "youtube", "v3", credentials=credentials, cache_discovery=False
        )
        self.assertIs(result, expected_client)

    def test_channel_verification_is_read_only(self):
        youtube = MagicMock()
        youtube.channels.return_value.list.return_value.execute.return_value = {
            "items": [{"id": "channel-id"}]
        }

        verify_channel_access(youtube)

        youtube.channels.return_value.list.assert_called_once_with(part="id", mine=True)
        youtube.videos.assert_not_called()

    def test_channel_verification_rejects_missing_channel(self):
        youtube = MagicMock()
        youtube.channels.return_value.list.return_value.execute.return_value = {"items": []}
        with self.assertRaisesRegex(OAuthConfigurationError, "exactly one"):
            verify_channel_access(youtube)


if __name__ == "__main__":
    unittest.main()
