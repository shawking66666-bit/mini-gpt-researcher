# Mini GPT Researcher 独立前端

在仓库根目录先启动 FastAPI（端口 `8000`），然后在此目录运行 `npm install`、`npm run dev`，打开 `http://127.0.0.1:5173/`。浏览器通过 Vite 的 `/api` 代理访问现有后端；前端不读取任何 API Key。

页面只实现一条混合检索主流程：选择 1–5 个 PDF/Markdown，填写研究主题，上传获得知识库 ID，发起研究，查看报告/计划/来源并下载 Markdown 或 HTML。研究接口是同步的，页面不显示实时内部阶段。

检查命令：`npm test -- --run`、`npm run build`、`npm run lint`。产品目标、页面行为和边界见仓库 `docs/2026-10-24-product-frontend-prd.md`。
