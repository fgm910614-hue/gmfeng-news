# GMFENG NEWS

每日 RSS 采集、去重、规则评分、中文翻译和静态发布。

## 免费中文翻译

使用开源 Argos Translate 英译中模型，在 GitHub Actions 运行器内翻译，不需要 Google Cloud、API Key 或银行卡。首次运行会下载模型并安装依赖，可能需要较长时间。翻译质量及 GitHub Actions 免费运行资源不作保证。

工作流 `.github/workflows/update-news.yml` 每日北京时间约 08:00 触发，也可在 Actions 中手动运行。GitHub 定时任务可能延迟。

翻译结果写入 `site/data/news.json` 的 `title_zh`、`summary_zh`，保留原文及来源链接。重复新闻尽量沿用上次译文；失败时保留原文，不中断新闻发布。`translated_count` 统计成功翻译或复用的条目。

## 部署

1. 将本升级包的 `collect.py`、`translate_news.py`、`site/index.html`、`.github/workflows/update-news.yml` 上传到仓库对应位置；不要覆盖线上已有的 `site/data/news.json`。
2. 进入 GitHub Actions → Update news → Run workflow。
3. 检查日志和 `site/data/news.json` 中的 `translated_count`、`translation_errors`。
4. 等待 Cloudflare Pages 自动部署，访问 `https://news.gmfeng.com` 检查中文标题和摘要。

**注意：** 不再需要 `GOOGLE_TRANSLATE_API_KEY`。若此前已配置，可在 GitHub Secrets 中删除该密钥。旧工作流中任何 Google 翻译环境变量都应去掉。
