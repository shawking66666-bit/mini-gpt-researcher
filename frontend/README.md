# Mini GPT Researcher 独立前端

这是项目默认演示页面，旧 Streamlit 页面作为历史客户端保留。完整的首次配置和密钥说明见[仓库根目录 README](../README.md#本地运行)。

首次在仓库根目录创建 `.venv`、安装 Python 依赖，自己配置根目录 `.env`，再到 `frontend/` 执行一次 `npm ci`。日常启动需保持两个 PowerShell 终端运行。

终端 1，在仓库根目录启动后端：

```powershell
.\.venv\Scripts\python.exe -m uvicorn mini_researcher.api:app --host 127.0.0.1 --port 8000
```

终端 2，从仓库根目录启动新网页：

```powershell
cd frontend
npm run dev -- --host 127.0.0.1
```

打开 `http://127.0.0.1:5173/`。Vite 通过 `/api` 代理访问本机 `8000` 端口；前端不读取任何 API Key。仓库不会提交 `.venv`、`.env`、`frontend/node_modules`，所以新克隆后必须先完成首次配置。此前临时复用旧实施工作区的 Python 环境，只是本机演示方式，不是标准启动步骤。

页面只实现一条混合检索主流程：选择 1–5 个 PDF/Markdown，填写研究主题，上传获得知识库 ID，发起研究，查看报告/计划/来源并下载 Markdown 或 HTML。研究接口是同步的，页面不显示实时内部阶段。

检查命令：`npm test -- --run`、`npm run build`、`npm run lint`。产品目标、页面行为和边界见仓库 `docs/2026-10-24-product-frontend-prd.md`。
