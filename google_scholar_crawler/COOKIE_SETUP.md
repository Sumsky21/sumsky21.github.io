# Google Scholar 引用数：SerpApi 设置

当前 GitHub Actions 使用 `ubuntu-latest`，通过 SerpApi 的
[Google Scholar Author API](https://serpapi.com/google-scholar-author-api)
获取 Google Scholar 作者页数据。SerpApi 是第三方服务，数据源仍是 Google Scholar。
工作流不再安装浏览器，也不需要浏览器 Cookie 或 ScraperAPI。

## 免费额度

截至 2026-10-21，[官方价格页](https://serpapi.com/pricing)列出：

- Free：每月 250 次查询，0 美元。
- Starter：每月 1,000 次查询，25 美元/月。

脚本每页请求最多 100 篇论文。一页即可返回的作者，每周更新一次约消耗每月 4～5 次查询；
分页、额外手动运行和成功的重复请求会增加用量。失败及缓存命中的查询按官方规则不计入额度。
先选择免费套餐即可，不需要为这次试运行购买付费套餐。

## 配置与运行

1. 在 [SerpApi](https://serpapi.com/) 注册免费账户，从控制台复制 API Key。
2. 打开仓库 **Settings → Secrets and variables → Actions → New repository secret**。
   添加 `SERPAPI_API_KEY`，值为该 Key。不要把 Key 写入代码或聊天。
3. 保留已有的 `GOOGLE_SCHOLAR_ID` Secret，它是作者页 URL 中 `user=` 后面的值。
4. 提交并推送本次代码后，进入 **Actions → Get Citation Data → Run workflow → main**，
   创建新任务。不要使用旧任务的 Re-run，因为它会继续运行旧版本配置。
5. 如果旧的 macOS 任务仍在排队，先取消它；相同 concurrency 分组中的旧运行可能挡住新任务。

也可以在本地通过 GitHub CLI 上传 Key（交互输入，不放在命令行参数中）：

```powershell
gh secret set SERPAPI_API_KEY --repo Sumsky21/sumsky21.github.io
```

自动更新频率仍为每周一 UTC 08:00（北京时间 16:00）。成功后发布
`gs_data.json` 与 `gs_data_shieldsio.json` 到 `google-scholar-stats` 分支，网页读取格式不变。

主页默认直接从 GitHub Raw 读取引用数，并禁用该 JSON 请求的浏览器缓存。
不要为这些动态数据启用 `google_scholar_stats_use_cdn`：jsDelivr 的分支缓存可能仍返回旧数据。
首次修改主页读取方式需要推送代码并等待 Pages 部署；后续引用数更新只需刷新页面。

## 失败时的行为

- 缺少 Key、认证失败或额度限制会明确报错。401/403 检查账户及 Key；429 检查月额度和小时限制。
- 网络错误和 HTTP 5xx 最多重试一次；整个抓取有 150 秒预算，Actions 抓取步骤限时 3 分钟。
- 自动处理分页，最多 10 页；响应缺少总引用数、论文列表或分页重复时停止，不发布不完整数据。
- 失败后保留上次成功发布的数据。日志不输出 API Key、完整请求 URL 或 API 原始响应。
- 本地自动测试使用模拟响应，不消耗查询额度；测试通过不代表实际服务请求已验证。

## 旧浏览器工具

`browser_fetch.py`、`scholar_cookies.py` 和 `upload_cookies.py` 暂时保留供本地诊断。
仅显式设置 `SCHOLAR_PROVIDER=browser` 才会使用旧抓取路径；该路径还需要自行安装 Playwright 浏览器。
默认及定时 Actions 均使用 `SCHOLAR_PROVIDER=serpapi`。
已有 `GOOGLE_SCHOLAR_COOKIE`、`GOOGLE_SCHOLAR_USER_AGENT`、`SCRAPER_API_KEY` Secret 不会被当前工作流读取。
