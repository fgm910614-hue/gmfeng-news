# GMFENG NEWS V2

部署：Cloudflare Pages，仓库根目录 `/`，输出目录 `site`，构建命令留空。上传整个项目覆盖旧仓库对应文件即可，保持 `.github/workflows/update-news.yml` 目录结构。

## 更新内容
- RSS 来源采集、跨媒体相似标题去重、36 小时时效窗口。
- 可选 OpenAI API：生成中文标题与摘要，辅助评分；保留原文和链接。未配置时保留英文原文，绝不伪装成中文 AI 翻译。
- GitHub Actions 每日 UTC 00:00（北京时间 08:00）触发，可能延迟；支持手动运行。
- 网站展示真实采集时间、翻译数量、来源数量、超过36小时未更新提示。
- 采集失败或少于10条时保留上次数据，避免发布空白页。

## 启用 AI 中文编译
GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret：
- Name: `OPENAI_API_KEY`
- Secret: 你自己创建的 OpenAI API Key（不要填入仓库文件或发给他人）。

本项目默认模型 `gpt-4.1-mini`，可在 workflow 的 `OPENAI_MODEL` 中修改。调用 API 可能产生费用，ChatGPT 订阅不包含 API 额度。请先确认 API 账户可用和计费限额。

## 验证
Actions → Update news → Run workflow。查看 Collect、Validate、Commit 三个步骤。网站页面底部显示翻译条数、来源数和采集时间。只有成功生成的新闻会写入 JSON。

## GMFENG 主站入口
在现有主站导航加入：`<a href="https://news.gmfeng.com/" target="_blank" rel="noopener noreferrer">全球资讯</a>`。
主站代码未包含在此仓库中，因此此入口需要在主站源码中修改，不应直接替换主站文件。

## 局限
相似标题去重是启发式，不保证完全合并跨语言同一事件；AI 评分不是事实核查；RSS 摘要不代表完整报道；中文翻译需人工抽查。新闻不足50条不强行补齐。首轮启用 AI 后需运行一次 Actions 才会看到中文。
