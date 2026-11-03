# GMFENG NEWS：自动中文翻译版

## 本次更新
- 保留现有 RSS 采集、评分、去重和每日更新。
- 新增 `translate_news.py`：Google Cloud Translation Basic v2 翻译英文标题与摘要，保留原文、链接。
- 优先复用上一版 JSON 中英文内容完全相同的翻译，减少重复计费。
- 翻译失败、未配置密钥或超过单次字符上限时显示英文原文，新闻仍照常发布。
- 网站继续优先显示 `title_zh`、`summary_zh`。

## 启用翻译（需要自行完成）
1. 在 Google Cloud 创建项目并关联结算账号。启用 **Cloud Translation API**。
2. 在 Google Cloud 的「API 和服务 → 凭据」创建 **API 密钥**，将密钥限制为仅可调用 **Cloud Translation API**。Basic v2 支持 API 密钥，**本方案不使用服务账号 JSON**。
3. GitHub 仓库 → Settings → Secrets and variables → Actions → New repository secret：
   - Name: `GOOGLE_TRANSLATE_API_KEY`
   - Secret: Google Cloud API 密钥（不要提交到代码仓库）
4. GitHub → Actions → Update news → Run workflow。检查 Collect news and translate to Chinese 是否成功。
5. 打开 `https://news.gmfeng.com/`，检查中文标题、摘要和网站底部翻译条数。

**费用注意**：Google Cloud 免费字符额度、适用条件和价格可能变化，需以 Google Cloud 控制台和官方定价为准。本项目的 `TRANSLATION_MAX_CHARS=450000` 只是**单次运行**安全上限，不是月度计费上限。建议在 Google Cloud 设置预算提醒和 API 配额，并监控每天实际使用量。GitHub 定时任务可能因重跑而增加费用。

## 技术说明
- 不需要额外 pip 包，使用 Python 标准库发起 HTTPS 请求。
- 每篇新闻翻译一次标题与摘要，摘要最多截取 1500 字符。
- 仅复用上一版 `news.json` 中完全一致的原文，**不是永久缓存**；跨多天的再次出现可能重新计费。
- 翻译失败时不会伪装成中文；`translation_errors` 记录错误类型。
- 如果 Google Cloud 访问或计费受限，保持未配置状态即可继续原文采集。
- 代码修改尚未部署到 GitHub，需要你上传本压缩包内的文件并配置密钥。
