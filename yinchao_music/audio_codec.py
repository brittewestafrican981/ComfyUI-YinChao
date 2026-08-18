"""Automatic MP3 <-> ComfyUI AUDIO conversion.

The node package uses PyAV, which ships the codec library through Python
packages and does not ask users to install a system ``ffmpeg`` command. The
ComfyUI AUDIO contract is a dict containing ``waveform`` and ``sample_rate``.
"""

from __future__ import annotations

from io import BytesIO
from typing import Any

from .errors import ConfigurationError, InvalidRequestError


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MP3_BITRATE = 192_000


class AudioCodec:
    def __init__(self) -> None:
        try:
            import av  # type: ignore
            import numpy as np  # type: ignore
            import torch  # type: ignore
        except ImportError as exc:
            raise ConfigurationError(
                "缺少自动音频编解码依赖 PyAV。请在 ComfyUI 的 Python 环境执行："
                "pip install -r requirements.txt，然后重启 ComfyUI。"
            ) from exc
        self.av = av
        self.np = np
        self.torch = torch

    def encode_mp3(self, audio: dict[str, Any]) -> bytes:
        waveform, sample_rate = self._validate_audio(audio)
        waveform = waveform.detach().to(device="cpu", dtype=self.torch.float32)
        if waveform.ndim == 2:
            waveform = waveform.unsqueeze(0)
        waveform = waveform[:1].clamp(-1.0, 1.0)
        channels = int(waveform.shape[1])
        if channels not in (1, 2):
            raise InvalidRequestError("参考音频目前只支持单声道或双声道 AUDIO 输入。")
        layout = "mono" if channels == 1 else "stereo"
        samples = waveform.numpy()[0].astype(self.np.float32, copy=False)

        output = BytesIO()
        with self.av.open(output, mode="w", format="mp3") as container:
            stream = container.add_stream("mp3", rate=sample_rate)
            stream.layout = layout
            stream.bit_rate = MP3_BITRATE
            frame = self.av.AudioFrame.from_ndarray(samples, format="fltp", layout=layout)
            frame.sample_rate = sample_rate
            for packet in stream.encode(frame):
                container.mux(packet)
            for packet in stream.encode(None):
                container.mux(packet)
        encoded = output.getvalue()
        if not encoded:
            raise InvalidRequestError("音频编码失败，MP3 内容为空。")
        return encoded

    def decode_mp3(self, encoded: bytes) -> dict[str, Any]:
        if not encoded:
            raise InvalidRequestError("下载的音频内容为空，无法解码。")
        frames = []
        sample_rate: int | None = None
        try:
            with self.av.open(BytesIO(encoded), mode="r") as container:
                for frame in container.decode(audio=0):
                    array = frame.to_ndarray(format="fltp").astype(self.np.float32)
                    if array.ndim == 1:
                        array = array.reshape(1, -1)
                    frames.append(array)
                    sample_rate = sample_rate or int(frame.sample_rate or 0)
        except self.av.error.FFmpegError as exc:
            raise InvalidRequestError("生成的音频不是可识别的 MP3/音频格式。") from exc

        if not frames or not sample_rate:
            raise InvalidRequestError("生成的音频没有可解码的采样数据。")
        waveform = self.np.concatenate(frames, axis=1)
        return {
            "waveform": self.torch.from_numpy(waveform).unsqueeze(0),
            "sample_rate": sample_rate,
        }

    def prepare_upload(self, audio: dict[str, Any]) -> bytes:
        encoded = self.encode_mp3(audio)
        if len(encoded) > MAX_UPLOAD_BYTES:
            raise InvalidRequestError(
                "编码后的参考音频超过 YinChao 文件上传限制 10 MB。"
                "请缩短音频后重试；节点不会擅自降低到不可控的质量。"
            )
        return encoded

    def _validate_audio(self, audio: dict[str, Any]) -> tuple[Any, int]:
        if not isinstance(audio, dict):
            raise InvalidRequestError("输入必须是 ComfyUI AUDIO 数据。")
        waveform = audio.get("waveform")
        sample_rate = audio.get("sample_rate")
        if waveform is None or not isinstance(sample_rate, (int, float)):
            raise InvalidRequestError("AUDIO 输入缺少 waveform 或 sample_rate。")
        if sample_rate <= 0:
            raise InvalidRequestError("AUDIO 的 sample_rate 必须大于 0。")
        if not hasattr(waveform, "ndim") or waveform.ndim not in (2, 3):
            raise InvalidRequestError("AUDIO waveform 必须是 [C,T] 或 [B,C,T]。")
        if waveform.ndim == 3 and int(waveform.shape[0]) != 1:
            raise InvalidRequestError("参考音频暂不支持批量 AUDIO；请只输入一首音频。")
        if int(waveform.shape[-1]) <= 0:
            raise InvalidRequestError("AUDIO waveform 不能为空。")
        return waveform, int(sample_rate)
