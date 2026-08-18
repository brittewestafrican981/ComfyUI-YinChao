"""Small, testable client for the YinChao Open API."""

from __future__ import annotations

import time
from dataclasses import dataclass
from ipaddress import ip_address
import socket
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlparse

import requests

from .config import DEFAULT_API_BASE_URL
from .errors import (
    ApiResponseError,
    AuthenticationError,
    InsufficientBalanceError,
    InvalidRequestError,
    ModerationError,
    TaskFailedError,
    TaskTimeoutError,
    TransportError,
    YinChaoError,
)


NORMAL_MODELS = ("v4.0", "v3.5")
REFERENCE_MODEL = "v3.5"
EXTEND_MODEL = "v3.5"
SIMILARITIES = (0.2, 0.8, 1.3, 1.5)
MAX_PROMPT_LENGTH = 1000
MAX_LYRIC_LENGTH = 3000
SONG_COUNT = 1


class HttpTransport(Protocol):
    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        """Perform an HTTP request."""


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    title: str
    lyric: str
    audio_url: str
    raw: Mapping[str, Any]


class RequestsTransport:
    """Production transport kept separate so tests never need network access."""

    def __init__(self) -> None:
        self.session = requests.Session()

    def request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        return self.session.request(method, url, **kwargs)


class YinChaoClient:
    """Synchronous API client used from the node's async worker thread.

    POST calls are intentionally never retried. A network failure after a
    paid submission must not silently create a second song. Only task-query
    GET requests can be retried by :meth:`poll_task`.
    """

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_API_BASE_URL,
        transport: HttpTransport | None = None,
        request_timeout: float = 30.0,
        poll_interval: float = 3.0,
        task_timeout: float = 600.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key.strip():
            raise AuthenticationError("YinChao API Key 为空，请在平台创建并配置有效的 API Key。")
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.transport = transport or RequestsTransport()
        self.request_timeout = request_timeout
        self.poll_interval = poll_interval
        self.task_timeout = task_timeout
        self.sleep = sleep

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "User-Agent": "YinChao-ComfyUI/1.0",
            "channel": "ComfyUI",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Mapping[str, Any] | None = None,
        params: Mapping[str, Any] | None = None,
        files: Mapping[str, Any] | None = None,
        data: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        request_headers = self._headers()
        if headers:
            request_headers.update(headers)
        url = path if path.startswith("http") else f"{self.base_url}/{path.lstrip('/')}"
        try:
            response = self.transport.request(
                method,
                url,
                headers=request_headers,
                json=json_body,
                params=params,
                files=files,
                data=data,
                timeout=self.request_timeout,
            )
        except requests.RequestException as exc:
            raise TransportError(f"无法连接 YinChao API：{exc}") from exc
        except OSError as exc:
            raise TransportError(f"无法连接 YinChao API：{exc}") from exc

        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code >= 400:
            raise self._http_error(status_code, self._response_message(response))

        if getattr(response, "content", b"") == b"" and not json_body and method == "GET":
            return response
        try:
            return response.json()
        except (AttributeError, ValueError, TypeError) as exc:
            raise ApiResponseError("YinChao API 返回了无法解析的 JSON 响应。") from exc

    @staticmethod
    def _response_message(response: Any) -> str:
        try:
            payload = response.json()
        except (AttributeError, ValueError, TypeError):
            payload = None
        if isinstance(payload, dict):
            for key in ("message", "error", "detail", "msg"):
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            nested = payload.get("data")
            if isinstance(nested, dict):
                for key in ("message", "error", "detail", "msg"):
                    value = nested.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
        return f"HTTP {getattr(response, 'status_code', 'unknown')}"

    @staticmethod
    def _http_error(status_code: int, message: str) -> YinChaoError:
        suffix = f"（{message}）" if message else ""
        if status_code in (401, 403):
            return AuthenticationError(
                f"YinChao API Key 无效或无权限{suffix}。请到平台检查 API Key："
                "https://platform.yinchaoyongxian.com/"
            )
        if status_code == 402:
            return InsufficientBalanceError(
                f"YinChao 账户余额不足{suffix}。请到平台充值后重试："
                "https://platform.yinchaoyongxian.com/"
            )
        if status_code == 422:
            return InvalidRequestError(f"YinChao 请求参数不合法{suffix}。")
        if status_code == 451:
            return ModerationError(f"YinChao 内容审核未通过{suffix}。请修改提示词或歌词。")
        if status_code in (429, 500, 502, 503, 504):
            return TransportError(f"YinChao 服务暂时不可用（HTTP {status_code}）{suffix}。")
        return YinChaoError(f"YinChao API 请求失败（HTTP {status_code}）{suffix}。")

    @staticmethod
    def _validate_text(prompt: str, lyric: str) -> tuple[str, str]:
        prompt = (prompt or "").strip()
        lyric = (lyric or "").strip()
        if len(prompt) > MAX_PROMPT_LENGTH:
            raise InvalidRequestError(f"提示词不能超过 {MAX_PROMPT_LENGTH} 个字符。")
        if len(lyric) > MAX_LYRIC_LENGTH:
            raise InvalidRequestError(f"歌词不能超过 {MAX_LYRIC_LENGTH} 个字符。")
        return prompt, lyric

    @staticmethod
    def _require_model(model: str, allowed: tuple[str, ...]) -> str:
        if model not in allowed:
            choices = ", ".join(allowed)
            raise InvalidRequestError(f"模型 {model!r} 不受支持，可选：{choices}。")
        return model

    def generate_lyrics(self, prompt: str) -> tuple[str, str]:
        prompt, _ = self._validate_text(prompt, "")
        if not prompt:
            raise InvalidRequestError("歌词生成需要填写提示词。")
        payload = self._request("POST", "/api/v1/lyric/generate", json_body={"prompt": prompt})
        body = self._unwrap_data(payload)
        title = self._string_value(body, "title")
        lyric = self._string_value(body, "lyric")
        if not lyric:
            raise ApiResponseError("歌词接口返回成功，但缺少 lyric 字段。")
        return title, lyric

    def submit_music(self, prompt: str, lyric: str = "", model: str = "v4.0") -> str:
        prompt, lyric = self._validate_text(prompt, lyric)
        self._require_model(model, NORMAL_MODELS)
        if not prompt and not lyric:
            raise InvalidRequestError("生歌至少需要填写提示词或歌词。")
        payload: dict[str, Any] = {
            "model": model,
            "task_type": "normal",
            "n": SONG_COUNT,
        }
        if prompt:
            payload["prompt"] = prompt
        if lyric:
            payload["lyric"] = lyric
        return self._extract_task_id(
            self._request("POST", "/api/v1/song/generate", json_body=payload)
        )

    def submit_reference(
        self,
        *,
        reference_upload_id: str,
        prompt: str = "",
        lyric: str = "",
        similarity: float = 0.8,
        model: str = REFERENCE_MODEL,
    ) -> str:
        prompt, lyric = self._validate_text(prompt, lyric)
        self._require_model(model, (REFERENCE_MODEL,))
        if similarity not in SIMILARITIES:
            choices = ", ".join(str(value) for value in SIMILARITIES)
            raise InvalidRequestError(f"仿写相似度必须是 {choices} 之一。")
        if not reference_upload_id.strip():
            raise InvalidRequestError("仿写需要有效的参考音频上传 ID。")
        payload: dict[str, Any] = {
            "model": model,
            "task_type": "reference",
            "reference_audio": {
                "audio_type": "upload_id",
                "audio_content": reference_upload_id.strip(),
            },
            "similarity": similarity,
            "n": SONG_COUNT,
        }
        if prompt:
            payload["prompt"] = prompt
        if lyric:
            payload["lyric"] = lyric
        return self._extract_task_id(
            self._request("POST", "/api/v1/song/generate", json_body=payload)
        )

    def submit_extend(
        self,
        *,
        origin_upload_id: str,
        lyric: str = "",
        extend_at: float | None = None,
        model: str = EXTEND_MODEL,
    ) -> str:
        _, lyric = self._validate_text("", lyric)
        self._require_model(model, (EXTEND_MODEL,))
        if not origin_upload_id.strip():
            raise InvalidRequestError("扩写需要有效的原始音频上传 ID。")
        payload: dict[str, Any] = {
            "model": model,
            "origin_audio": {
                "audio_type": "upload_id",
                "audio_content": origin_upload_id.strip(),
            },
            "n": SONG_COUNT,
        }
        if lyric:
            payload["lyric"] = lyric
        if extend_at is not None:
            if extend_at < 0:
                raise InvalidRequestError("扩写起始时间不能小于 0 秒；留空表示从歌曲结尾续写。")
            payload["extend_at"] = extend_at
        return self._extract_task_id(
            self._request("POST", "/api/v1/song/extend", json_body=payload)
        )

    def upload_audio(self, audio_bytes: bytes, *, filename: str, upload_type: str) -> str:
        if not audio_bytes:
            raise InvalidRequestError("音频编码结果为空，无法上传。")
        payload = self._request(
            "POST",
            "/api/v1/file/upload",
            files={"file": (filename, audio_bytes, "audio/mpeg")},
            data={"upload_type": upload_type},
        )
        body = self._unwrap_data(payload)
        upload_id = self._string_value(body, "id") or self._string_value(body, "upload_id")
        if not upload_id:
            raise ApiResponseError("文件上传接口返回成功，但缺少上传 ID。")
        return upload_id

    def get_task(self, task_id: str) -> Mapping[str, Any]:
        payload = self._request(
            "GET", "/api/v1/task/query", params={"task_id": task_id.strip()}
        )
        body = self._unwrap_data(payload)
        if not isinstance(body, Mapping):
            raise ApiResponseError("任务查询接口返回的数据格式不正确。")
        return body

    def poll_task(self, task_id: str) -> TaskResult:
        task_id = task_id.strip()
        if not task_id:
            raise ApiResponseError("任务提交成功，但没有返回 task_id。")
        deadline = time.monotonic() + self.task_timeout
        consecutive_get_failures = 0
        while time.monotonic() < deadline:
            try:
                task = self.get_task(task_id)
                consecutive_get_failures = 0
            except (TransportError, YinChaoError) as exc:
                # Only task-query GETs are retried. No POST is replayed here.
                if not self._is_safe_poll_error(exc) or consecutive_get_failures >= 3:
                    raise
                consecutive_get_failures += 1
                self.sleep(min(2**consecutive_get_failures, 8))
                continue

            status = self._task_status(task)
            if status in {"fail", "failed", "error", "cancel", "cancelled"}:
                detail = self._task_error(task)
                raise TaskFailedError(
                    f"YinChao 任务 {task_id} 失败{f'：{detail}' if detail else '。'}"
                )
            if status == "done":
                result = self._task_result(task, task_id)
                if result is None:
                    raise ApiResponseError("任务已完成，但响应中没有可下载的音频地址。")
                return result
            if status not in {"pending", "running", "stream", ""}:
                raise TaskFailedError(f"YinChao 返回未知任务状态：{status!r}。")
            self.sleep(self.poll_interval)
        raise TaskTimeoutError(
            f"YinChao 任务 {task_id} 超过 {int(self.task_timeout)} 秒仍未完成。"
        )

    def generate_music_and_wait(
        self, prompt: str, lyric: str = "", model: str = "v4.0"
    ) -> TaskResult:
        return self.poll_task(self.submit_music(prompt, lyric, model))

    def reference_and_wait(
        self,
        *,
        reference_upload_id: str,
        prompt: str = "",
        lyric: str = "",
        similarity: float = 0.8,
        model: str = REFERENCE_MODEL,
    ) -> TaskResult:
        return self.poll_task(
            self.submit_reference(
                reference_upload_id=reference_upload_id,
                prompt=prompt,
                lyric=lyric,
                similarity=similarity,
                model=model,
            )
        )

    def extend_and_wait(
        self,
        *,
        origin_upload_id: str,
        lyric: str = "",
        extend_at: float | None = None,
        model: str = EXTEND_MODEL,
    ) -> TaskResult:
        return self.poll_task(
            self.submit_extend(
                origin_upload_id=origin_upload_id,
                lyric=lyric,
                extend_at=extend_at,
                model=model,
            )
        )

    def download_audio(self, audio_url: str) -> bytes:
        if not audio_url or not audio_url.startswith(("http://", "https://")):
            raise ApiResponseError("任务结果中的 audio_url 不是有效的 HTTP(S) 地址。")
        parsed = urlparse(audio_url)
        self._validate_download_host(parsed)
        base_host = urlparse(self.base_url).hostname or ""
        headers = (
            self._headers()
            if (parsed.hostname or "").lower().rstrip(".") == base_host.lower().rstrip(".")
            else {"Accept": "audio/mpeg"}
        )
        try:
            response = self.transport.request(
                "GET",
                audio_url,
                headers=headers,
                timeout=self.request_timeout,
            )
        except (requests.RequestException, OSError) as exc:
            raise TransportError(f"无法下载生成的音频：{exc}") from exc
        status_code = int(getattr(response, "status_code", 0) or 0)
        if status_code >= 400:
            raise TransportError(f"下载生成的音频失败（HTTP {status_code}）。")
        content = getattr(response, "content", b"")
        if not isinstance(content, bytes) or not content:
            raise ApiResponseError("音频下载成功，但内容为空。")
        return content

    def _validate_download_host(self, parsed: Any) -> None:
        hostname = (parsed.hostname or "").lower().rstrip(".")
        base_url = urlparse(self.base_url)
        base_host = (base_url.hostname or "").lower().rstrip(".")
        if not hostname:
            raise ApiResponseError("任务结果中的 audio_url 缺少主机名。")
        if parsed.username or parsed.password:
            raise ApiResponseError("任务结果中的 audio_url 不允许包含用户名或密码。")
        if parsed.scheme != "https" and not (
            hostname == base_host and base_url.scheme == "http"
        ):
            raise ApiResponseError("外部 audio_url 必须使用 HTTPS。")
        if hostname == base_host:
            return
        if hostname in {"localhost", "localhost.localdomain"} or hostname.endswith(
            (".localhost", ".local", ".internal")
        ):
            raise TransportError("为保护 ComfyUI 主机安全，已拒绝内部 audio_url。")
        try:
            addresses = {ip_address(info[4][0]) for info in socket.getaddrinfo(hostname, 443)}
        except socket.gaierror as exc:
            raise TransportError(f"无法解析音频地址主机名 {hostname!r}。") from exc
        if any(
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_unspecified
            or address.is_reserved
            for address in addresses
        ):
            raise TransportError("为保护 ComfyUI 主机安全，已拒绝指向内网地址的 audio_url。")

    @classmethod
    def _unwrap_data(cls, payload: Any) -> Any:
        if not isinstance(payload, Mapping):
            return payload
        data = payload.get("data")
        return data if data is not None else payload

    @staticmethod
    def _string_value(value: Any, key: str) -> str:
        if not isinstance(value, Mapping):
            return ""
        candidate = value.get(key)
        return candidate.strip() if isinstance(candidate, str) else ""

    @classmethod
    def _extract_task_id(cls, payload: Any) -> str:
        body = cls._unwrap_data(payload)
        if isinstance(body, Mapping):
            for key in ("task_id", "id"):
                task_id = cls._string_value(body, key)
                if task_id:
                    return task_id
        raise ApiResponseError("歌曲任务提交成功，但响应中缺少 task_id/id。")

    @classmethod
    def _task_result(cls, task: Mapping[str, Any], task_id: str) -> TaskResult | None:
        candidates: list[Any] = [task]
        for key in ("data", "result", "choices", "songs", "outputs"):
            value = task.get(key)
            if isinstance(value, list):
                candidates.extend(value)
            elif isinstance(value, Mapping):
                candidates.append(value)
        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            audio_url = cls._string_value(candidate, "audio_url")
            if not audio_url:
                continue
            return TaskResult(
                task_id=task_id,
                title=cls._string_value(candidate, "title"),
                lyric=cls._string_value(candidate, "lyric"),
                audio_url=audio_url,
                raw=candidate,
            )
        return None

    @classmethod
    def _task_status(cls, task: Mapping[str, Any]) -> str:
        """Normalize both documented query shapes.

        The current API returns ``choices`` where each song owns a status;
        some deployments also expose a top-level status. With n=1, a failed
        choice is terminal and must not be treated as an endless empty poll.
        """

        top_level = str(task.get("status", "")).lower().strip()
        if top_level in {"done", "fail", "failed", "error", "cancel", "cancelled"}:
            return top_level
        choices = task.get("choices")
        if not isinstance(choices, list) or not choices:
            return top_level
        statuses = [
            str(choice.get("status", "")).lower().strip()
            for choice in choices
            if isinstance(choice, Mapping)
        ]
        if any(status == "done" for status in statuses):
            return "done"
        if statuses and all(
            status in {"fail", "failed", "error", "cancel", "cancelled"}
            for status in statuses
        ):
            return "fail"
        if any(status == "stream" for status in statuses):
            return "stream"
        if any(status == "running" for status in statuses):
            return "running"
        if any(status == "pending" for status in statuses):
            return "pending"
        return top_level

    @classmethod
    def _task_error(cls, task: Mapping[str, Any]) -> str:
        detail = cls._string_value(task, "error") or cls._string_value(task, "message")
        choices = task.get("choices")
        if isinstance(choices, list):
            for choice in choices:
                if isinstance(choice, Mapping):
                    detail = detail or cls._string_value(choice, "error")
                    if detail:
                        break
        return detail

    @staticmethod
    def _is_safe_poll_error(error: YinChaoError) -> bool:
        # Only retry errors that are known to be transient. Authentication,
        # balance, moderation and validation failures must reach the user.
        return isinstance(error, TransportError)
