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

## 2026-11-10 公开阅读器升级

公开入口仍为 `https://news.gmfeng.com`。此版本沿用原有 GitHub Actions 日采集、Argos 翻译、全球来源及中国/亚洲软目标，不改变 `.github/workflows/update-news.yml`、`feeds.json` 或当期 `site/data/news.json`。

新版采用与 GMFENG 私有阅读版一致的极简排版，增加多条件搜索筛选、地区多标签、未读、收藏、最新排序、列表/卡片、深色模式与事件详情。收藏和进度仅保存在访客浏览器；旧版收藏与主题偏好可迁移。首发50篇报道的中文标题与摘要经过校读，后续新闻沿用上游译文并标注校读状态。

`web/news.ts` 在浏览器中合并72小时内相同事件，保留全部来源链接，分开保留评论和政策后果。地区按事件地点与参与方识别，不按媒体所在地推断。重要性采用公共影响4分、影响范围3分、持续影响2分、报道广度1分，详情可查，分数不代表可信度。

`functions/api/image.js` 是 Cloudflare Pages 的受限图片读取入口，仅允许已列出的媒体 HTTPS 域名，不跟随重定向，校验图片类型与大小。`site/_routes.json` 只将 `/api/image` 交给函数，其他页面和数据保持静态。首发批次可用图片已缓存；转发读取失败时允许浏览器直接读取同一白名单中的原图，仍无法取得的图片采用固定尺寸、明确标注的主题占位图。

前端源码在 `web/`，已编译文件位于 `site/assets/`，带内容散列以防缓存旧版。修改前端后运行：

```sh
npm ci
npm test
npx tsc --noEmit
npm run build
```

将源码、函数和编译资源一并提交即可触发原 Cloudflare Pages Git 部署，构建输出目录保持 `site`。日采集不依赖 Node 构建，也不会重写前端资源。新增 `Check public reader` 负责检查源码与提交资源是否一致。
