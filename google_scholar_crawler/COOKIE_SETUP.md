# 在 GitHub Actions 中抓取 Google Scholar：匿名 / Cookie 对照

数据仍来自 Google Scholar。GitHub 托管 runner 使用 Playwright 启动所选浏览器，
默认在全新浏览器上下文中匿名访问，不导入本机 Cookie，不使用 ScraperAPI。

## 当前默认：匿名访问

推送代码后，从 **Actions → Get Citation Data → Run workflow → main** 创建新任务。
选择 `auth_mode: anonymous`；`browser` 选择与上次测试相同的浏览器，以便只比较 Cookie 的影响。
日志会明确显示 `[anonymous]`。

当前已切换为 GitHub 托管的 `macos-15`，并非本地 Mac。
本次与 Ubuntu 作对照时，请选择 `auth_mode: anonymous`、`browser: webkit`，
与上次 Ubuntu 上的 WebKit 匿名请求保持一致，只更换 runner 环境。

匿名模式只需要 `GOOGLE_SCHOLAR_ID` Secret。已有的 `GOOGLE_SCHOLAR_COOKIE` 无需删除，
该模式不会将它传给抓取进程，也不会读取它。站点在访问过程中正常设置的 Cookie 仍由浏览器管理。
每周定时任务也默认匿名访问。

若要对照原来的 Cookie 模式，手动选择 `auth_mode: cookie`；日志会显示 `[imported-cookie]`。
此模式才会读取现有 Cookie Secret。以下是 Cookie 模式的可选设置步骤。

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
5. 不需要复制 `User-Agent`：runner 使用所选浏览器自己生成的标头。

## 3. 在仓库根目录运行上传脚本

```powershell
python google_scholar_crawler/upload_cookies.py
```

脚本提示后粘贴 Cookie 并回车，输入内容不会显示。它通过 `gh secret set` 的标准输入
上传到 `Sumsky21/sumsky21.github.io` 的 `GOOGLE_SCHOLAR_COOKIE` Secret。
脚本只依赖 Python 标准库和 GitHub CLI。

之前上传的 `GOOGLE_SCHOLAR_USER_AGENT` Secret 不再使用。

也可从只包含 Cookie 请求头值的单行 UTF-8 文件读取：

```powershell
python google_scholar_crawler/upload_cookies.py --file "$env:USERPROFILE\Downloads\scholar-cookies.txt"
```

其他仓库可加 `--repo owner/repository`。不要把 Cookie 粘贴到聊天、代码或 Actions 日志中；
Cookie 含浏览器会话凭据，应只从本机上传到你信任的私有 Secret 存储。

## 4. 运行 Actions

推送代码后，从 **Actions → Get Citation Data → Run workflow → main** 创建新任务。
在 `browser` 下拉框选择 `firefox` 可检验 Firefox；也支持 `chromium` 和 `webkit`。
默认和每周定时任务仍使用 `chromium`，单次手动选择不会改变定时任务配置。
如果 Firefox 的真实抓取成功，可再将 workflow 中定时任务的默认浏览器切换为 Firefox。
保留现有 `GOOGLE_SCHOLAR_ID` Secret；不再需要 `SCRAPER_API_KEY`。
默认 `auth_mode` 为 `anonymous`；只有选择 `cookie` 时才使用上传的 Cookie。
脚本上传 Cookie 不会自动推送代码或触发 workflow。

workflow 固定使用 GitHub 托管的 `macos-15`。每次运行只安装所选 Playwright 浏览器，
先执行单元测试和该浏览器的模拟页面测试，再抓取引用数据。现有每周一的定时触发保持不变。
本次匿名对照只需要推送代码并创建新任务，无需上传 Cookie。

抓取步骤由 Actions 原生 `timeout-minutes: 3` 限时，无需 macOS 额外安装 GNU `timeout`。
整个 job 的超时仍为 10 分钟。切换 runner 不代表已解决 Scholar 的 403，需以真实抓取日志为准。

成功时仍写入 `results/gs_data.json` 和 `results/gs_data_shieldsio.json`，
随后 workflow 发布到 `google-scholar-stats` 分支。

Cookie 可能过期，Google 也可能根据 runner 的出口 IP 再次要求验证。
换用 Firefox 可以检验浏览器引擎差异，但并不保证解除 IP 级限制。
出现明确的 403、429 或验证码时程序会停止，保留上一次成功发布的引用数据。
仅网络超时和服务器 5xx 会重试一次。日志只记录状态，不保存 Cookie、浏览器状态或页面截图。
如果所选浏览器仍返回 403，这说明此托管环境中的浏览器请求也被拒绝，
不能据此判定 Cookie 已过期，也不应通过无限重试掩盖失败。
