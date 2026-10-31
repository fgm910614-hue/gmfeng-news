# GMFENG NEWS · Cloudflare Pages 免费静态版

## 这版与之前 Python 服务器版的区别

不需要购买服务器。GitHub Actions 每天北京时间约 08:10 尝试读取公开 RSS，生成 `site/data/news.json` 并提交到仓库。Cloudflare Pages 自动重新部署。GitHub 定时任务可能延迟或跳过，不能保证精确时间。Cloudflare Pages 只托管静态 HTML/JSON。

## 1. GitHub
1. 登录 https://github.com ，新建仓库 `gmfeng-news`（Public 可节约 Actions 额度，注意代码公开）。
2. 将 ZIP 解压后 **压缩包内的所有文件及 `.github` 文件夹** 上传到仓库根目录。GitHub 网页上传时要确保隐藏的 `.github` 文件夹被包含；若无法上传文件夹，使用 GitHub 网页新建 `.github/workflows/update-news.yml` 并粘贴文件内容。
3. 打开 Actions，允许工作流；进入 Update news，点击 Run workflow，等待成功。查看 `site/data/news.json` 是否出现真实新闻。首次任务可能因外部 RSS 网络错误失败，此时不会编造新闻。

## 2. Cloudflare Pages
1. 登录 https://dash.cloudflare.com ，进入 Workers & Pages → Create → Pages → Connect to Git。
2. 选择 `gmfeng-news` 仓库；Production branch 选 main。
3. Framework preset: None；Build command: 留空；Build output directory: `site`。
4. 部署后获得类似 `gmfeng-news.pages.dev` 的临时地址。

## 3. 阿里云 DNS
1. Cloudflare Pages 项目 → Custom domains → Set up a domain → 输入 `news.gmfeng.com`。
2. 阿里云域名 DNS 新增 CNAME：主机记录 `news`，记录值填写 **Cloudflare Pages 实际分配给你的** `项目名.pages.dev`。不要修改现有 `@` 或 `www` 记录。
3. 等待域名和 HTTPS 证书生效，再测试 `https://news.gmfeng.com`。
4. 在原 GMFENG 网站编辑器增加导航 `<a href="https://news.gmfeng.com">全球资讯</a>`。

## 说明
- 评分为启发式关键词估计，**不是 AI 语义评分**；没有自动中文翻译或事件级语义去重。
- 目标每日 30–50 条，实际以抓到的可核实新闻为准，不足时不会虚构。
- 收藏使用浏览器 localStorage，不跨设备同步。
- 网站静态资源可免费托管，但 RSS 访问、Actions 执行、Pages 构建都受平台额度和可用性限制。
- 使用公开 RSS 仍需遵守新闻来源使用条款。
