# Registry 发布准备 / Registry publishing checklist

当前仓库已完成 GitHub 代码推送；Comfy Registry 发布仍需单独执行。

当前版本使用 MIT License，许可证文件位于仓库根目录的 `LICENSE`，并已在 `pyproject.toml` 中声明。

Comfy Registry 需要两个不能凭空猜测的身份字段：

```toml
[project.urls]
Repository = "https://github.com/yinhcao/ComfyUI-YinChao"

[tool.comfy]
PublisherId = "yinhcao"
```

以上字段已按当前 GitHub 仓库和发布者账号配置，发布前完成以下检查：

1. GitHub 仓库默认分支包含 `yinchao_music/`、`requirements.txt`、`pyproject.toml`、`README.md` 和 `workflows/`。
2. `Repository` 指向真实公开 GitHub 仓库；`PublisherId` 使用已认领的发布者身份。
3. 在目标 ComfyUI V3 环境运行 5 个示例 Workflow，确认设置页、API Key、native `AUDIO` 和任务错误显示均正常。
4. 记录实际通过验收的 ComfyUI 版本，再决定是否补充 `[tool.comfy] requires-comfyui`；当前没有用未经实测的版本号伪造最低版本。
5. 再按 Comfy Registry 文档执行登录、校验和发布。

API Key、账户余额和用户数据不应进入 Git、Workflow、截图或发布包。
