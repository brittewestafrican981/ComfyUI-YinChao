"""Modern ComfyUI V3 nodes for YinChao music generation."""

from __future__ import annotations

import asyncio

from comfy_api.latest import ComfyExtension, io, ui

from .api_client import (
    EXTEND_MODEL,
    NORMAL_MODELS,
    REFERENCE_MODEL,
    SIMILARITIES,
    TaskResult,
    YinChaoClient,
)
from .audio_codec import AudioCodec
from .config import resolve_api_key


CATEGORY = "YinChao/Music"


def _client() -> YinChaoClient:
    return YinChaoClient(resolve_api_key())


def _song_output(
    node_cls: type[io.ComfyNode], client: YinChaoClient, result: TaskResult, lyric_fallback: str
) -> io.NodeOutput:
    # The API returns MP3. Decode it once into the native ComfyUI AUDIO
    # contract so downstream audio/video nodes can connect without a manual
    # download or conversion step.
    codec = AudioCodec()
    audio_bytes = client.download_audio(result.audio_url)
    audio = codec.decode_mp3(audio_bytes)
    title = result.title or "YinChao Song"
    lyric = result.lyric or lyric_fallback or ""
    return io.NodeOutput(
        audio,
        title,
        lyric,
        result.audio_url,
        result.task_id,
        ui=ui.PreviewAudio(audio, cls=node_cls),
    )


class YinChaoGenerateLyrics(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="YinChaoGenerateLyrics",
            display_name="YinChao Generate Lyrics",
            category=CATEGORY,
            description="使用音潮 API 生成歌词。用法说明：platform.yinchaoyongxian.com",
            not_idempotent=True,
            inputs=[
                io.String.Input(
                    "prompt",
                    display_name="Prompt / 提示词",
                    multiline=True,
                    default="",
                    placeholder="Describe the theme, language and mood / 描述主题、语言和情绪",
                )
            ],
            outputs=[
                io.String.Output(display_name="title / 标题"),
                io.String.Output(display_name="lyrics / 歌词"),
            ],
        )

    @classmethod
    async def execute(cls, prompt: str) -> io.NodeOutput:
        title, lyric = await asyncio.to_thread(_client().generate_lyrics, prompt)
        return io.NodeOutput(title, lyric)


class YinChaoGenerateMusic(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="YinChaoGenerateMusic",
            display_name="YinChao Generate Music",
            category=CATEGORY,
            description="输入提示词/歌词生成一首歌曲（每次执行固定 n=1）。",
            not_idempotent=True,
            inputs=[
                io.Combo.Input(
                    "model",
                    display_name="Model / 模型",
                    options=list(NORMAL_MODELS),
                    default="v4.0",
                ),
                io.String.Input(
                    "prompt",
                    display_name="Prompt / 风格提示词",
                    multiline=True,
                    default="",
                    optional=True,
                ),
                io.String.Input(
                    "lyric",
                    display_name="Lyrics / 歌词（可选）",
                    multiline=True,
                    default="",
                    optional=True,
                ),
            ],
            outputs=[
                io.Audio.Output(display_name="audio / 音频"),
                io.String.Output(display_name="title / 标题"),
                io.String.Output(display_name="lyric / 歌词"),
                io.String.Output(display_name="audio_url / 音频地址"),
                io.String.Output(display_name="task_id / 任务 ID"),
            ],
        )

    @classmethod
    async def execute(cls, model: str, prompt: str = "", lyric: str = "") -> io.NodeOutput:
        client = _client()
        result = await asyncio.to_thread(client.generate_music_and_wait, prompt, lyric, model)
        return await asyncio.to_thread(_song_output, cls, client, result, lyric)


class YinChaoReferenceMusic(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="YinChaoReferenceMusic",
            display_name="YinChao Reference Music",
            category=CATEGORY,
            description="使用输入 AUDIO 仿写一首歌曲；平台会按参考音频相似度计费。",
            not_idempotent=True,
            inputs=[
                io.Audio.Input("audio", display_name="Reference AUDIO / 参考音频"),
                io.Combo.Input(
                    "similarity",
                    display_name="Similarity / 相似度",
                    options=list(SIMILARITIES),
                    default=0.8,
                ),
                io.String.Input(
                    "prompt",
                    display_name="Prompt / 风格补充（可选）",
                    multiline=True,
                    default="",
                    optional=True,
                ),
                io.String.Input(
                    "lyric",
                    display_name="Lyrics / 歌词（可选）",
                    multiline=True,
                    default="",
                    optional=True,
                ),
            ],
            outputs=[
                io.Audio.Output(display_name="audio / 音频"),
                io.String.Output(display_name="title / 标题"),
                io.String.Output(display_name="lyric / 歌词"),
                io.String.Output(display_name="audio_url / 音频地址"),
                io.String.Output(display_name="task_id / 任务 ID"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        audio: dict,
        similarity: float = 0.8,
        prompt: str = "",
        lyric: str = "",
    ) -> io.NodeOutput:
        client = _client()
        codec = AudioCodec()
        encoded = await asyncio.to_thread(codec.prepare_upload, audio)
        upload_id = await asyncio.to_thread(
            client.upload_audio,
            encoded,
            filename="yinchao-reference.mp3",
            upload_type="reference",
        )
        result = await asyncio.to_thread(
            client.reference_and_wait,
            reference_upload_id=upload_id,
            prompt=prompt,
            lyric=lyric,
            similarity=float(similarity),
            model=REFERENCE_MODEL,
        )
        return await asyncio.to_thread(_song_output, cls, client, result, lyric)


class YinChaoExtendMusic(io.ComfyNode):
    @classmethod
    def define_schema(cls) -> io.Schema:
        return io.Schema(
            node_id="YinChaoExtendMusic",
            display_name="YinChao Extend Music",
            category=CATEGORY,
            description="从输入 AUDIO 的结尾继续扩写，或指定秒数作为扩写起点。",
            not_idempotent=True,
            inputs=[
                io.Audio.Input("audio", display_name="Origin AUDIO / 原始音频"),
                io.Float.Input(
                    "extend_at",
                    display_name="Extend at seconds / 起始秒数（可选）",
                    default=None,
                    min=0.0,
                    step=0.1,
                    optional=True,
                ),
                io.String.Input(
                    "lyric",
                    display_name="Lyrics / 扩写歌词（可选）",
                    multiline=True,
                    default="",
                    optional=True,
                ),
            ],
            outputs=[
                io.Audio.Output(display_name="audio / 音频"),
                io.String.Output(display_name="title / 标题"),
                io.String.Output(display_name="lyric / 歌词"),
                io.String.Output(display_name="audio_url / 音频地址"),
                io.String.Output(display_name="task_id / 任务 ID"),
            ],
        )

    @classmethod
    async def execute(
        cls,
        audio: dict,
        extend_at: float | None = None,
        lyric: str = "",
    ) -> io.NodeOutput:
        client = _client()
        codec = AudioCodec()
        encoded = await asyncio.to_thread(codec.prepare_upload, audio)
        upload_id = await asyncio.to_thread(
            client.upload_audio,
            encoded,
            filename="yinchao-origin.mp3",
            upload_type="extend",
        )
        result = await asyncio.to_thread(
            client.extend_and_wait,
            origin_upload_id=upload_id,
            lyric=lyric,
            extend_at=extend_at,
            model=EXTEND_MODEL,
        )
        return await asyncio.to_thread(_song_output, cls, client, result, lyric)


class YinChaoMusicExtension(ComfyExtension):
    async def get_node_list(self) -> list[type[io.ComfyNode]]:
        return [
            YinChaoGenerateLyrics,
            YinChaoGenerateMusic,
            YinChaoReferenceMusic,
            YinChaoExtendMusic,
        ]


async def comfy_entrypoint() -> YinChaoMusicExtension:
    return YinChaoMusicExtension()
