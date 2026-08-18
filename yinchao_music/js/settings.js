import { app } from "../../../scripts/app.js";

app.registerExtension({
  name: "YinChao Music",
  settings: [
    {
      id: "YinChao.apiKey",
      name: "YinChao API Key / 音潮 API Key",
      type: "text",
      defaultValue: "",
      attrs: {
        type: "password",
        autocomplete: "off",
      },
      tooltip:
        "注册、充值并创建 API Key： https://platform.yinchaoyongxian.com/ 。密钥保存在 ComfyUI 用户设置，不会写入 Workflow。",
    },
  ],
});
