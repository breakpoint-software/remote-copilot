from slack.responses import SLACK_MESSAGE_LIMIT, post_thread_response


class FakeClient:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.files: list[dict] = []

    def chat_postMessage(self, **kwargs):
        self.messages.append(kwargs)

    def files_upload_v2(self, **kwargs):
        self.files.append(kwargs)


def test_posts_message_at_limit() -> None:
    client = FakeClient()
    text = "x" * SLACK_MESSAGE_LIMIT

    post_thread_response(client, "C1", "123.4", text)

    assert client.messages == [{"channel": "C1", "thread_ts": "123.4", "text": text}]
    assert client.files == []


def test_uploads_file_above_limit() -> None:
    client = FakeClient()
    text = "á" * (SLACK_MESSAGE_LIMIT + 1)

    post_thread_response(client, "C1", "123.4", text, filename="codex-response.md")

    assert client.messages == []
    assert client.files[0]["channel"] == "C1"
    assert client.files[0]["thread_ts"] == "123.4"
    assert client.files[0]["filename"] == "codex-response.md"
    assert client.files[0]["content"] == text.encode("utf-8")
