# 在 GitHub Actions 中使用浏览器 Cookie 抓取 Google Scholar

数据仍来自 Google Scholar。Actions 直接访问 Scholar，不使用 ScraperAPI。
本地脚本将浏览器请求的 Cookie 上传为仓库 Actions Secret。

## 1. 准备 GitHub CLI

在 Windows 上安装 GitHub CLI，重新打开终端后登录：

```powershell
winget install --id GitHub.cli --exact
gh auth login
```

## 2. 从浏览器获取 Scholar 请求的 Cookie

1. 用 Chrome、Edge 或 Firefox 打开自己的 Scholar 页面：
   `https://scholar.google.com/citations?user=PV3IC6wAAAAJ&hl=en&pagesize=100`。
2. 如果遇到验证码，先在浏览器中手动完成，确认页面正常显示。
3. 按 F12 打开开发者工具，切到 **Network / 网络**，刷新页面。
4. 选择主文档 `citations?...` 请求，在 **Request Headers / 请求标头** 中复制
   `Cookie` 的值。复制的是请求的 Cookie，不是响应的 `Set-Cookie`，也不是
   `document.cookie`（后者可能漏掉 HttpOnly Cookie）。
5. 可同时记录该请求的 `User-Agent` 值。

## 3. 在仓库根目录运行上传脚本

```powershell
python google_scholar_crawler/upload_cookies.py
```

脚本提示后粘贴 Cookie 并回车，输入内容不会显示。它通过 `gh secret set` 的标准输入
上传到 `Sumsky21/sumsky21.github.io` 的 `GOOGLE_SCHOLAR_COOKIE` Secret。
脚本只依赖 Python 标准库和 GitHub CLI。

如需同时传递相同浏览器的 User-Agent：

```powershell
python google_scholar_crawler/upload_cookies.py --user-agent '从浏览器复制的完整 User-Agent'
```

也可从只包含 Cookie 请求头值的单行 UTF-8 文件读取：

```powershell
python google_scholar_crawler/upload_cookies.py --file "$env:USERPROFILE\Downloads\scholar-cookies.txt"
```

其他仓库可加 `--repo owner/repository`。不要把 Cookie 粘贴到聊天、代码或 Actions 日志中；
Cookie 含浏览器会话凭据，应只从本机上传到你信任的私有 Secret 存储。

## 4. 运行 Actions

推送代码后，从 **Actions → Get Citation Data → Run workflow → main** 创建新任务。
保留现有 `GOOGLE_SCHOLAR_ID` Secret；不再需要 `SCRAPER_API_KEY`。
脚本上传 Cookie 不会自动推送代码或触发 workflow。

成功时仍写入 `results/gs_data.json` 和 `results/gs_data_shieldsio.json`，
随后 workflow 发布到 `google-scholar-stats` 分支。

Cookie 可能过期，Google 也可能根据 IP、TLS 或浏览器特征再次要求验证。
所以本机浏览器有效的 Cookie 并不保证在 GitHub runner 上可用。若出现验证码、
重定向、403 或 429，程序会停止；更新 Cookie 后再运行。如果持续被拦截，
需要在本机或使用相同网络的 self-hosted runner 执行抓取。
