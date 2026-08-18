# YinChao Music for ComfyUI

[中文](README.md)

YinChao Music nodes for modern ComfyUI V3. The plugin exposes lyric generation, prompt-to-song, reference generation, and song extension. Generated MP3 files are decoded automatically into native `AUDIO` values so they can connect to other audio, video, and subtitle nodes.

## Installation

### ComfyUI Manager / Registry

This repository contains the Registry metadata and example Workflows. The source code is hosted on [GitHub](https://github.com/yinhcao/ComfyUI-YinChao). See [REGISTRY_PUBLISHING.md](REGISTRY_PUBLISHING.md) for the remaining Comfy Registry publishing steps.

### Manual installation

Place the repository directory at:

```text
ComfyUI/custom_nodes/yinchao-music/
```

Install the dependencies in the Python environment used by ComfyUI, then restart ComfyUI:

```bash
python -m pip install -r requirements.txt
```

`av` provides the Python audio codec integration. Users do not need to install a system-level `ffmpeg` command; the plugin does not require a separate codec download or configuration.

## Configure the API key

1. Open the [YinChao Platform](https://platform.yinchaoyongxian.com/) and sign up or sign in.
2. Add balance or purchase credits on the platform, then create an API key.
3. In ComfyUI, open Settings → YinChao → API Key and save the key.

The key is not a node input and is never written to Workflow JSON. For headless environments, use the environment variable:

```bash
export YINCHAO_API_KEY="your-api-key"
```

The configuration priority is ComfyUI user settings, the local user configuration file, and then `YINCHAO_API_KEY`. Missing or invalid keys, insufficient balance, invalid parameters, content moderation failures, task failures, and timeouts stop the node with an explicit error instead of returning an empty success value.

The plugin calls `https://open.yinchaoyongxian.com`; the platform link above is used for account registration, balance, and API-key onboarding.

## Four nodes

| Node | Inputs | Outputs |
| --- | --- | --- |
| `YinChao Generate Lyrics` | Prompt | title, lyrics |
| `YinChao Generate Music` | model (default `v4.0`), prompt, optional lyrics | native `AUDIO`, title, lyric, audio_url, task_id |
| `YinChao Reference Music` | native `AUDIO`, similarity, optional prompt/lyrics | native `AUDIO`, title, lyric, audio_url, task_id |
| `YinChao Extend Music` | native `AUDIO`, optional start time/lyrics | native `AUDIO`, title, lyric, audio_url, task_id |

Song nodes always submit `n=1`. This avoids the platform default of `n=2`, which could generate two songs and charge twice for one execution. The nodes submit the asynchronous task, poll its status, download the MP3, and decode it internally; users do not need separate submit, wait, download, or convert nodes.

`Reference Music` and `Extend Music` automatically encode input native `AUDIO` as MP3 before uploading. The upload limit follows the YinChao API limit of 10 MB; oversized input fails explicitly instead of silently changing its quality. Generated results are decoded to native `AUDIO` without an additional output compression step.

## Official combined Workflows

The repository includes five examples:

1. `workflows/lyrics_to_music.json`: lyric generation → song generation (official combination)
2. `workflows/lyrics_example.json`: standalone lyric generation
3. `workflows/music_example.json`: standalone prompt-to-song generation
4. `workflows/reference_example.json`: standalone reference generation
5. `workflows/extend_example.json`: standalone song extension

The combined Workflow only connects lyric text and contains no API key. Configure the Settings page after importing it, then run the song node that incurs platform charges.

## API and billing notes

The current API paths covered by this plugin are:

- `POST /api/v1/lyric/generate`: standalone lyric generation;
- `POST /api/v1/song/generate`: `normal` song generation or `reference` generation;
- `POST /api/v1/song/extend`: song extension;
- `POST /api/v1/file/upload`: reference or source audio upload;
- `GET /api/v1/task/query`: asynchronous task polling.

Song-node calls are charged according to the platform account rules. The current documentation lists approximately `¥0.22` per song for song/reference/extension generation and `¥0.07` per standalone lyric request. Check the platform account and current documentation for the latest pricing.

## Development validation

The tests do not call the live API and do not consume account credits:

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall -q yinchao_music tests
node --check js/settings.js
git diff --check
```

The nodes use the V3 schema from `comfy_api.latest` and do not retain the legacy `NODE_CLASS_MAPPINGS` or legacy input compatibility layer. Before real use, validate once in the target ComfyUI installation by configuring the key, running a test Workflow, and checking the `AUDIO` output; offline tests do not replace that acceptance check.

## References

- [YinChao Platform](https://platform.yinchaoyongxian.com/)
- [YinChao prompt-to-song API](https://platform-alpha.yinchaoyongxian.com/zh/docs/guides/prompt-generate)
- [YinChao reference generation API](https://platform-alpha.yinchaoyongxian.com/zh/docs/guides/reference-generate)
- [YinChao song extension API](https://platform-alpha.yinchaoyongxian.com/zh/docs/guides/extend-song)
- [ComfyUI V3 Migration](https://docs.comfy.org/custom-nodes/v3_migration)
- [ComfyUI AUDIO datatype](https://docs.comfy.org/custom-nodes/backend/datatypes)

## License

This project is released under the [MIT License](LICENSE).
