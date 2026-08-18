# YinChao Music for ComfyUI

音潮音乐节点（ComfyUI V3）。插件把音潮开放平台的歌词、生歌、仿写和扩写能力接入 ComfyUI，并将生成结果转换成原生 `AUDIO`，可以继续连接音频、视频和字幕节点。

YinChao Music nodes for modern ComfyUI V3. The plugin exposes lyric generation, prompt-to-song, reference generation, and song extension. Generated MP3 files are decoded automatically into native `AUDIO` values.

## 安装 / Install

### ComfyUI Manager / Registry

本仓库包含 Registry 所需的 `pyproject.toml` 和示例 Workflow。当前代码托管在 [GitHub](https://github.com/yinhcao/ComfyUI-YinChao)，后续按 [REGISTRY_PUBLISHING.md](REGISTRY_PUBLISHING.md) 完成 Comfy Registry 发布。

This repository contains Registry metadata and workflow examples. The GitHub repository and publisher metadata are configured; publishing to Comfy Registry remains a separate step.

### 手动安装 / Manual

将仓库目录放到：

```text
ComfyUI/custom_nodes/yinchao-music/
```

在 ComfyUI 使用的 Python 环境中安装依赖，然后重启 ComfyUI：

```bash
python -m pip install -r requirements.txt
```

`av` 是 Python 音频编解码依赖。用户不需要自行安装系统 `ffmpeg` 命令；插件不会要求手动下载或配置系统编解码器。

## 配置 API Key / Configure the API Key

1. 打开 [音潮开放平台](https://platform.yinchaoyongxian.com/)，注册/登录。
2. 在平台完成账户充值或购买额度，再创建 API Key。
3. 在 ComfyUI 的 Settings → YinChao → API Key 中填写密钥并保存。

密钥不会作为节点输入，也不会写入 Workflow JSON。无图形界面时可以使用环境变量：

```bash
export YINCHAO_API_KEY="your-api-key"
```

配置优先级是 ComfyUI 用户设置、本地用户配置文件、`YINCHAO_API_KEY` 环境变量。缺少密钥、密钥无效、余额不足、参数错误、内容审核失败、任务失败和超时都会以明确错误中止节点，不会返回空字符串假装成功。

The plugin calls the API host `https://open.yinchaoyongxian.com`; the website above is the account, recharge, and API-key onboarding page.

## 四个节点 / Four nodes

| 节点 | 输入 | 输出 |
| --- | --- | --- |
| `YinChao Generate Lyrics` | Prompt | title, lyrics |
| `YinChao Generate Music` | model（默认 `v4.0`）、prompt、可选歌词 | native `AUDIO`, title, lyric, audio_url, task_id |
| `YinChao Reference Music` | native `AUDIO`、similarity、可选 prompt/歌词 | native `AUDIO`, title, lyric, audio_url, task_id |
| `YinChao Extend Music` | native `AUDIO`、可选起始秒数/歌词 | native `AUDIO`, title, lyric, audio_url, task_id |

每次歌曲类节点执行固定提交 `n=1`，避免平台默认 `n=2` 导致一次执行生成两首并产生双倍费用。节点内部负责提交异步任务、轮询任务状态、下载 MP3 并解码；用户不需要再拼接 submit/wait/download/convert 节点。

`Reference Music` 和 `Extend Music` 会把输入的 native `AUDIO` 自动编码为 MP3 后上传。上传限制按音潮接口的 10 MB 执行；超限会明确报错，不会悄悄改变输入质量。生成结果只解码为 native `AUDIO`，不会为了输出再次压缩。

## 官方组合 Workflow / Official combined workflow

仓库提供 5 个示例：

1. `workflows/lyrics_to_music.json`：歌词生成 → 生歌（官方组合）
2. `workflows/lyrics_example.json`：独立歌词生成
3. `workflows/music_example.json`：独立提示词生歌
4. `workflows/reference_example.json`：独立仿写
5. `workflows/extend_example.json`：独立扩写

组合 Workflow 只连接歌词文本，不包含 API Key。导入后先配置设置，再执行会产生平台费用的歌曲节点。

## API 与计费提示 / API and billing

当前适配的 API 路径：

- `POST /api/v1/lyric/generate`：独立歌词生成；
- `POST /api/v1/song/generate`：`normal` 生歌或 `reference` 仿写；
- `POST /api/v1/song/extend`：扩写；
- `POST /api/v1/file/upload`：上传参考/原始音频；
- `GET /api/v1/task/query`：查询异步任务。

歌曲类调用按平台实际账户规则计费；文档当前标注生歌/仿写/扩写约 `¥0.22/首`，独立歌词约 `¥0.07/次`。请以平台账户和最新文档为准。

## 开发验证 / Offline validation

本仓库测试不调用真实 API，也不会消耗账户额度：

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
python3 -m compileall -q yinchao_music tests
node --check js/settings.js
git diff --check
```

节点使用 `comfy_api.latest` 的 V3 schema，不保留旧版 `NODE_CLASS_MAPPINGS` 或旧节点输入兼容层。实际运行前需要在目标 ComfyUI 安装中做一次真实的“配置 Key → 执行测试 Workflow → 检查 AUDIO 输出”验收；本仓库的离线测试不会替代这一步。

## 相关文档 / References

- [音潮平台](https://platform.yinchaoyongxian.com/)
- [音潮提示词生歌接口](https://platform-alpha.yinchaoyongxian.com/zh/docs/guides/prompt-generate)
- [音潮仿写接口](https://platform-alpha.yinchaoyongxian.com/zh/docs/guides/reference-generate)
- [音潮扩写接口](https://platform-alpha.yinchaoyongxian.com/zh/docs/guides/extend-song)
- [ComfyUI V3 Migration](https://docs.comfy.org/custom-nodes/v3_migration)
- [ComfyUI AUDIO datatype](https://docs.comfy.org/custom-nodes/backend/datatypes)
