from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from yinchao_music.api_client import YinChaoClient
from yinchao_music.config import resolve_api_key
from yinchao_music.errors import (
    InsufficientBalanceError,
    TaskFailedError,
    TransportError,
)


class FakeResponse:
    def __init__(self, payload=None, *, status_code=200, content=b"{}"):
        self.payload = payload
        self.status_code = status_code
        self.content = content

    def json(self):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class QueueTransport:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


class ApiClientTests(unittest.TestCase):
    def test_prompt_submission_is_single_song_and_poll_uses_query_params(self):
        transport = QueueTransport(
            [
                FakeResponse({"id": "task-123"}),
                FakeResponse(
                    {
                        "status": "done",
                        "audio_url": "https://cdn.example.test/song.mp3",
                        "title": "Test Song",
                        "lyric": "hello",
                    }
                ),
            ]
        )
        client = YinChaoClient(
            "secret-key",
            transport=transport,
            poll_interval=0,
            task_timeout=1,
            sleep=lambda _: None,
        )

        result = client.generate_music_and_wait("bright pop", "hello", "v4.0")

        post_kwargs = transport.calls[0][2]
        self.assertEqual(post_kwargs["json"]["n"], 1)
        self.assertEqual(post_kwargs["json"]["task_type"], "normal")
        self.assertNotIn("api_key", post_kwargs["json"])
        self.assertEqual(post_kwargs["headers"]["channel"], "ComfyUI")
        self.assertEqual(transport.calls[1][2]["params"], {"task_id": "task-123"})
        self.assertEqual(transport.calls[1][2]["headers"]["channel"], "ComfyUI")
        self.assertEqual(result.audio_url, "https://cdn.example.test/song.mp3")
        self.assertEqual(result.task_id, "task-123")

    def test_task_failure_is_not_converted_to_empty_output(self):
        transport = QueueTransport(
            [
                FakeResponse({"task_id": "task-fail"}),
                FakeResponse({"status": "fail", "error": "moderation"}),
            ]
        )
        client = YinChaoClient("secret-key", transport=transport, sleep=lambda _: None)
        with self.assertRaises(TaskFailedError):
            client.generate_music_and_wait("bad", model="v4.0")

    def test_documented_choices_status_shape_is_supported(self):
        transport = QueueTransport(
            [
                FakeResponse({"id": "task-choice"}),
                FakeResponse(
                    {
                        "id": "task-choice",
                        "choices": [
                            {
                                "id": "song-1",
                                "status": "done",
                                "audio_url": "https://cdn.example.test/song.mp3",
                            }
                        ],
                    }
                ),
            ]
        )
        client = YinChaoClient(
            "secret-key", transport=transport, poll_interval=0, sleep=lambda _: None
        )
        result = client.generate_music_and_wait("documented response shape")
        self.assertEqual(result.task_id, "task-choice")

    def test_balance_error_is_typed(self):
        transport = QueueTransport([FakeResponse({"message": "balance",}, status_code=402)])
        client = YinChaoClient("secret-key", transport=transport)
        with self.assertRaises(InsufficientBalanceError):
            client.submit_music("hello")

    def test_settings_take_priority_over_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            user_dir = Path(directory)
            settings_dir = user_dir / "default"
            settings_dir.mkdir()
            (settings_dir / "comfy.settings.json").write_text(
                json.dumps({"YinChao.apiKey": "settings-key"}), encoding="utf-8"
            )
            with patch.dict(
                os.environ,
                {
                    "COMFYUI_USER_DIRECTORY": str(user_dir),
                    "YINCHAO_API_KEY": "environment-key",
                },
                clear=False,
            ):
                self.assertEqual(resolve_api_key(), "settings-key")

    def test_environment_is_headless_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {
                    "COMFYUI_USER_DIRECTORY": directory,
                    "YINCHAO_API_KEY": "environment-key",
                },
                clear=False,
            ):
                self.assertEqual(resolve_api_key(), "environment-key")

    def test_all_settings_win_over_an_earlier_local_fallback(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            first_dir = Path(first) / "default"
            second_dir = Path(second) / "default"
            first_dir.mkdir()
            second_dir.mkdir()
            (first_dir / "yinchao.json").write_text(
                json.dumps({"api_key": "old-local-key"}), encoding="utf-8"
            )
            (second_dir / "comfy.settings.json").write_text(
                json.dumps({"YinChao.apiKey": "current-settings-key"}), encoding="utf-8"
            )
            with patch("yinchao_music.config._candidate_user_directories", return_value=[Path(first), Path(second)]):
                self.assertEqual(resolve_api_key(), "current-settings-key")

    def test_private_audio_download_target_is_rejected_before_transport(self):
        transport = QueueTransport([])
        client = YinChaoClient("secret-key", transport=transport)
        with self.assertRaises(TransportError):
            client.download_audio("https://127.0.0.1/private.mp3")
        self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
