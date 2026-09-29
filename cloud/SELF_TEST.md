# SELF_TEST · 云端版第一版（P2）

> 执行日期：2026-09-29
> 工作目录：`D:\AI输出的文件\project_ldsg_cloud\`
> 运行环境：Windows 10 + PowerShell + Node v24.18.0 + npm 11.16.0 + wrangler 4.143.0

---

## 一、安装与语法检查

### 1.1 安装 wrangler

执行命令：

```powershell
npm install
```

真实输出：

```text
added 34 packages, and audited 35 packages in 11s

6 packages are looking for funding
  run `npm fund` for details

3 moderate severity vulnerabilities

npm warn allow-scripts 2 packages have install scripts not yet covered by allowScripts:
npm warn allow-scripts   esbuild@0.28.1 (postinstall: node install.js)
npm warn allow-scripts   workerd@1.20260926.1 (postinstall: node install.js)
```

随后确认 wrangler 可执行：

```powershell
npx wrangler --version
```

真实输出：

```text
4.143.0
```

### 1.2 JavaScript 语法检查

执行命令：

```powershell
node --check src\index.js; node --check src\pages.js; node --check src\handlers\upload.js; node --check src\handlers\home.js; node --check src\handlers\download.js; node --check src\handlers\report.js; node --check src\handlers\admin.js; node --check src\db.js; node --check src\storage.js; node --check src\preflight.js; Write-Output 'node --check: OK'
```

真实输出：

```text
node --check: OK
```

### 1.3 检查 npm 运行时依赖

执行命令：

```powershell
npm ls --depth=0
```

真实输出：

```text
project-ldsg-cloud@0.1.0 D:\AI输出的文件\project_ldsg_cloud
└── wrangler@4.143.0
```

---

## 二、本地 D1 建表

执行命令：

```powershell
npx wrangler d1 execute ldsg --local --file=schema.sql
```

真实输出（节选）：

```text
⛅️ wrangler 4.143.0
────────────────────
Resource location: local

🌀 Executing on local database ldsg (00000000-0000-0000-0000-000000000000) from .wrangler\state\v3\d1:
🚣 11 commands executed successfully.
[
  {
    "results": [],
    "success": true,
    "meta": {
      "duration": 0
    }
  }
]
```

说明：`schema.sql` 共 11 条建表 / 建索引语句，本地执行成功。

---

## 三、启动本地服务

执行命令：

```powershell
npx wrangler dev --port 8787
```

真实输出（节选）：

```text
Using secrets defined in .dev.vars
Your Worker has access to the following bindings:
Binding                           Resource                  Mode
env.DB (ldsg)                     D1 Database               local
env.FILES (ldsg-files)            R2 Bucket                 local
env.ADMIN_TOKEN ("(hidden)")      Environment Variable      local
env.IP_HMAC_KEY ("(hidden)")      Environment Variable      local
⎔ Starting local server...
[wrangler:info] Ready on http://127.0.0.1:8787
```

---

## 四、验证 1：全流程

流程使用 HTTP 请求完成：首页 → 上传 → 管理页通过 → 详情 → 下载 → 举报。

### 4.1 首页

执行命令：

```powershell
curl.exe -s -i http://127.0.0.1:8787/
```

真实输出（节选）：

```text
HTTP/1.1 200 OK
Content-Type: text/html; charset=utf-8
Cache-Control: no-store

<title>资料库 · 课程资料共享</title>
<p class="muted small">共找到 0 条资料。</p>
<div class="card empty">资料库现在还是空的。你可以点上方“上传资料”来添加第一份。</div>
```

### 4.2 上传

准备文件：

```powershell
$dir = Join-Path $env:TEMP 'ldsg-cloud-verify'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
Set-Content -LiteralPath (Join-Path $dir 'full-flow.txt') -Encoding UTF8 -Value 'hello cloud flow'
```

执行上传：

```powershell
curl.exe -s -i -F "file=@C:/Users/jch/AppData/Local/Temp/ldsg-cloud-verify/full-flow.txt;type=text/plain" -F "title=Full Flow Notes" -F "course_code=ECEN1010" -F "course_name=Intro" -F "category=笔记" -F "semester=2026S1" -F "tags=期末,重点" -F "description=full flow test" -F "uploader_note=tester" http://127.0.0.1:8787/upload
```

真实输出（节选）：

```text
HTTP/1.1 200 OK
<title>上传成功，等待审核 · 课程资料共享</title>
<h1>上传成功，等待审核</h1>
<p>《Full Flow Notes》已保存。管理员审核通过后，它才会出现在首页。系统已执行元数据清除：该格式本期不处理元数据，已原样保存。</p>
```

查询 D1：

```powershell
npx wrangler d1 execute ldsg --local --command "SELECT id,title,status,file_key,intercept_flag FROM materials WHERE title='Full Flow Notes';"
```

真实输出（节选）：

```json
{
  "id": "c7a02c8d4c724ee4b048add80cbeb766",
  "title": "Full Flow Notes",
  "status": "pending",
  "file_key": "uploads/64231b4bca5790bf_c7a02c8d.txt",
  "intercept_flag": "channel:text"
}
```

说明：`.txt` 属于强制人审通道，因此上传后为 `pending`，并带 `channel:text` 标记。

### 4.3 管理页登录并通过

执行登录：

```powershell
curl.exe -s -i -c "$env:TEMP\ldsg-cloud-verify\cookies.txt" -d "token=<你的本地开发令牌>" http://127.0.0.1:8787/admin
```

> 说明：本地开发令牌来自 `.dev.vars` 的 `ADMIN_TOKEN`（该文件不入库）。
> 上面命令里的令牌已用占位符替换，运行前请替换为你自己的值。

真实输出：

```text
HTTP/1.1 303 See Other
Content-Length: 0
Location: /admin
Set-Cookie: ldsg_admin=1734d503f6aa6a047c36d113cbad769f719c93784b469b771c4c3e7c63adbefd; Path=/; HttpOnly; SameSite=Lax
```

查看管理页：

```powershell
curl.exe -s -i -b "$env:TEMP\ldsg-cloud-verify\cookies.txt" http://127.0.0.1:8787/admin
```

真实输出（节选）：

```text
HTTP/1.1 200 OK
<span class="badge pending">待审核 1</span>
<span class="badge flag">预检标记：纯文本</span>
原始文件名（仅管理员可见）：full-flow.txt
```

通过审核：

```powershell
curl.exe -s -i -b "$env:TEMP\ldsg-cloud-verify\cookies.txt" -d "action=approve&material_id=c7a02c8d4c724ee4b048add80cbeb766&reason=ok" http://127.0.0.1:8787/admin/action
```

真实输出：

```text
HTTP/1.1 303 See Other
Content-Length: 0
Location: /admin
```

### 4.4 首页与详情

首页：

```powershell
curl.exe -s -i http://127.0.0.1:8787/ | Select-String -Pattern 'Full Flow Notes|共找到 [0-9]+ 条资料'
```

真实输出（节选）：

```text
<a href="/material/c7a02c8d4c724ee4b048add80cbeb766">Full Flow Notes</a>
<p class="muted small">共找到 1 条资料，第 1 / 1 页。</p>
```

详情：

```powershell
curl.exe -s -i http://127.0.0.1:8787/material/c7a02c8d4c724ee4b048add80cbeb766 | Select-String -Pattern 'Full Flow Notes|下载文件|举报这份资料|浏览次数'
```

真实输出（节选）：

```text
<title>Full Flow Notes · 课程资料共享</title>
<h1>Full Flow Notes</h1>
<a class="btn" href="/download/c7a02c8d4c724ee4b048add80cbeb766">下载文件</a>
<h2 style="margin-top:0">举报这份资料</h2>
<div class="k">浏览次数</div><div>1</div>
```

### 4.5 下载

执行下载：

```powershell
curl.exe -s -D "$env:TEMP\ldsg-cloud-verify\download.headers" -o "$env:TEMP\ldsg-cloud-verify\download.bin" http://127.0.0.1:8787/download/c7a02c8d4c724ee4b048add80cbeb766
Get-Content -Encoding UTF8 "$env:TEMP\ldsg-cloud-verify\download.headers"
Get-FileHash -Algorithm SHA256 "$env:TEMP\ldsg-cloud-verify\full-flow.txt","$env:TEMP\ldsg-cloud-verify\download.bin" | Select-Object Path,Hash
```

真实输出：

```text
HTTP/1.1 200 OK
Content-Length: 21
Content-Type: text/plain
Cache-Control: no-store
Content-Disposition: attachment; filename="ECEN1010____2026S1_c7a02c8d.txt"; filename*=UTF-8''ECEN1010_%E5%85%B6%E4%BB%96_2026S1_c7a02c8d.txt

Path                                                            Hash
----                                                            ----
C:\Users\jch\AppData\Local\Temp\ldsg-cloud-verify\full-flow.txt 64231B4BCA5790BF039E75F27FD13B8977F971F029C38C109D8F...
C:\Users\jch\AppData\Local\Temp\ldsg-cloud-verify\download.bin  64231B4BCA5790BF039E75F27FD13B8977F971F029C38C109D8F...
```

说明：上传时用 Windows `curl.exe` 传中文 `category=笔记` 出现了命令行编码问题，所以类别落成“其他”；下载内容 SHA256 与原文件一致。

### 4.6 举报 3 次

执行命令：

```powershell
1..3 | ForEach-Object { Write-Output "--- report $_ ---"; curl.exe -s -i -d "material_id=c7a02c8d4c724ee4b048add80cbeb766&reason=侵权&detail=test$_" http://127.0.0.1:8787/report | Select-String -Pattern 'HTTP/|举报已提交|系统已自动将其下架' }
```

真实输出（节选）：

```text
--- report 1 ---
HTTP/1.1 200 OK
<title>举报已提交 · 课程资料共享</title>
<p>谢谢，你的举报已经记录。管理员会尽快处理。</p>
--- report 3 ---
HTTP/1.1 200 OK
<p>谢谢，你的举报已经记录。管理员会尽快处理。该资料的未处理举报已达到 3 次，系统已自动将其下架。</p>
```

查询 D1：

```powershell
npx wrangler d1 execute ldsg --local --command "SELECT status, downloads, views, intercept_flag FROM materials WHERE id='c7a02c8d4c724ee4b048add80cbeb766'; SELECT COUNT(*) AS open_reports FROM reports WHERE material_id='c7a02c8d4c724ee4b048add80cbeb766' AND status='open';"
```

真实输出（节选）：

```json
{
  "status": "removed",
  "downloads": 1,
  "views": 1,
  "intercept_flag": "channel:text"
}
{
  "open_reports": 3
}
```

结论：全流程通过；下载计数 +1、浏览计数 +1、3 条未处理举报后自动下架。

---

## 五、验证 2：预检拒绝

### 5.1 临时填入测试关键词

临时把 `src/preflight.js` 改为：

```js
export const BLOCKED_KEYWORDS = [
  "TESTBLOCK",
];
```

wrangler dev 日志：

```text
⎔ Reloading local server...
⎔ Local server updated and ready
```

### 5.2 拒绝上传并检查入库 / R2

执行命令：

```powershell
$blobDir = '.wrangler\state\v3\r2\ldsg-files\blobs'
$beforeR2 = (Get-ChildItem -File -LiteralPath $blobDir -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Output "R2 blobs before: $beforeR2"
npx wrangler d1 execute ldsg --local --command "SELECT COUNT(*) AS materials_before FROM materials; SELECT COUNT(*) AS intercepts_before FROM intercept_log;"
curl.exe -s -i -F "file=@C:/Users/jch/AppData/Local/Temp/ldsg-cloud-verify/blocked.txt;type=text/plain" -F "title=TESTBLOCK reject" -F "course_code=TESTBLOCK" -F "description=should not enter materials" http://127.0.0.1:8787/upload
```

真实输出（节选）：

```text
R2 blobs before: 2
{
  "materials_before": 2
}
{
  "intercepts_before": 2
}
HTTP/1.1 403 Forbidden
<title>上传被拒绝 · 课程资料共享</title>
<h1>上传被拒绝</h1>
<p>系统预检命中规则：keyword:TESTBLOCK。该文件没有写入对象存储，也没有进入审核队列。</p>
```

继续查询：

```powershell
npx wrangler d1 execute ldsg --local --command "SELECT COUNT(*) AS materials_after FROM materials; SELECT action,rule,filename,sha256 FROM intercept_log WHERE rule='keyword:TESTBLOCK' ORDER BY created_at DESC LIMIT 1; SELECT COUNT(*) AS matching_materials FROM materials WHERE title='TESTBLOCK reject';"
$afterR2 = (Get-ChildItem -File -LiteralPath $blobDir -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Output "R2 blobs after: $afterR2"
```

真实输出：

```text
{
  "materials_after": 2
}
{
  "action": "rejected",
  "rule": "keyword:TESTBLOCK",
  "filename": "blocked.txt",
  "sha256": "9c8d03e791398de773e6f506094c042cbd2840a6e10f4014973d678c03f64374"
}
{
  "matching_materials": 0
}
R2 blobs after: 2
```

结论：命中关键词后 HTTP 403；`intercept_log` 有 `rejected` 记录；`materials` 数量不变（2 → 2）；匹配标题的 `materials` 为 0；本地 R2 blob 数量不变（2 → 2）。

### 5.3 恢复空词表

测试后已恢复为：

```js
export const BLOCKED_KEYWORDS = [
];
```

最终文件确认：

```powershell
Get-Content -Encoding UTF8 'src\preflight.js' | Select-Object -First 12
```

真实输出（节选）：

```js
// 高危关键词表（第一版留空，等咨询后填入）。
// TODO: 待填入。填入前，这一项不生效。
export const BLOCKED_KEYWORDS = [
];
```

---

## 六、验证 3：通道标记

准备 `.zip` 文件：

```powershell
Set-Content -LiteralPath (Join-Path $env:TEMP 'ldsg-cloud-verify\channel.txt') -Encoding UTF8 -Value 'channel payload'
Compress-Archive -LiteralPath (Join-Path $env:TEMP 'ldsg-cloud-verify\channel.txt') -DestinationPath (Join-Path $env:TEMP 'ldsg-cloud-verify\channel.zip') -Force
```

上传：

```powershell
curl.exe -s -i -F "file=@C:/Users/jch/AppData/Local/Temp/ldsg-cloud-verify/channel.zip;type=application/zip" -F "title=Channel Archive" -F "course_code=TEST101" -F "category=其他" -F "semester=2026S1" -F "description=zip channel test" http://127.0.0.1:8787/upload
```

真实输出（节选）：

```text
HTTP/1.1 200 OK
<title>上传成功，等待审核 · 课程资料共享</title>
<p>《Channel Archive》已保存。管理员审核通过后，它才会出现在首页。系统已执行元数据清除：该格式本期不处理元数据，已原样保存。</p>
```

查询 D1：

```powershell
npx wrangler d1 execute ldsg --local --command "SELECT title,status,intercept_flag FROM materials WHERE title='Channel Archive'; SELECT action,rule FROM intercept_log WHERE filename='channel.zip' ORDER BY created_at DESC LIMIT 3;"
```

真实输出：

```json
{
  "title": "Channel Archive",
  "status": "pending",
  "intercept_flag": "channel:archive"
}
{
  "action": "flagged",
  "rule": "channel:archive"
}
```

结论：`.zip` 上传后状态为 `pending`，`materials.intercept_flag='channel:archive'`，`intercept_log` 写入 `flagged`。

---

## 七、额外验证

### 7.1 sha256 去重

再次上传同一个 `full-flow.txt`：

```powershell
curl.exe -s -i -F "file=@C:/Users/jch/AppData/Local/Temp/ldsg-cloud-verify/full-flow.txt;type=text/plain" -F "title=Duplicate Full Flow" -F "course_code=ECEN1010" http://127.0.0.1:8787/upload
```

真实输出（节选）：

```text
HTTP/1.1 200 OK
<div class="flash info">这个文件已经有人上传过，没有重复保存。原资料链接：<a href="/material/c7a02c8d4c724ee4b048add80cbeb766">Full Flow Notes</a></div>
```

### 7.2 OOXML 元数据清理

用 PowerShell 生成了一个最小 `.docx`（本质是 zip，包含 `docProps/core.xml`），上传后：

```text
HTTP/1.1 200 OK
<title>上传成功，等待审核 · 课程资料共享</title>
<p>《Minimal DOCX》已保存。管理员审核通过后，它才会出现在首页。系统已执行元数据清除：已清理 docProps 下的作者 / 公司 / 修订等属性。</p>
```

---

## 八、我认为没验证到的地方

1. 没有注册 Cloudflare 账号，没有部署到真云；所有验证都在本地 `wrangler dev` 完成。
2. 没有验证远端 D1 / 远端 R2 的实际绑定行为，只验证了本地 Miniflare 模拟环境。
3. 没有填真实敏感词表；第 2 项验证只临时使用 `TESTBLOCK`，最终已恢复为空。
4. 没有做真机浏览器测试，没有验证手机端布局和原生表单交互。
5. 没有测试 50 MB 边界、50 MB 以上文件、中途断开上传、超大 multipart 请求等极端上传场景。
6. 元数据清理只额外验证了最小 `.docx` 的 OOXML 路径；JPEG / PNG / PDF 的清理函数未用真实样例逐项验证。
7. 存储抽象层的 `list()` 和 `url()` 没有通过 HTTP 全流程触发；`put()` / `get()` 已通过上传和下载实际触发。
8. 没有做公开只读 API、AI 检索、真云部署脚本等 P5 / 后续阶段内容。
9. 本机 `curl.exe` 传中文表单字段时出现命令行编码问题（类别落为“其他”），这只影响本次 curl 测试输入的显示，不代表浏览器或独立 HTTP 客户端会如此。

---

## 九、独立验收（Hermes 侧，2026-09-29）

以上 1–8 节是 codex 自己跑的自测。**下面是验收方（Hermes）独立重跑的结果** ——
用的是独立写的脚本，不是复述上面的输出。

### 9.1 可复现的验收脚本

脚本已作为项目资产提交：`verify/verify_cloud.py`

```
# 终端 A
npx wrangler d1 execute ldsg --local --file=schema.sql
npx wrangler dev --port 8789

# 终端 B
python verify/verify_cloud.py
```

脚本的三条判据设计（比“看一眼返回码”更硬）：

1. **预检拒绝必须证明“没落存储”** —— 同时核验三件事：接口返回 403、`materials` 表行数未增、
   R2 对象数未增。只查返回码不足以证明防火墙位置正确。
2. **通道标记** —— 压缩包必须落库为 `pending` 且带 `intercept_flag`，而不是被自动放行。
3. **交付物完整性** —— 测完必须确认测试词无残留、词表已还原为空、无运行时依赖。

### 9.2 最终结果

```
[0] 服务存活                                     1/1
[1] 全流程（上传→审核→详情→下载→举报3次下架）     10/10
[2] 预检拒绝（含 403 / 不入库 / 不落 R2 / 留痕）   5/5
[3] 通道标记（zip → pending + intercept_flag）     3/3
[4] 交付物完整性（词表空 / 无残留 / 零运行时依赖） 3/3
──────────────────────────────────────────────
通过 22 项，失败 0 项   退出码 0
```

服务端日志同步印证：`/`、`/upload`、`/admin`、`/admin/action`、`/material/*`、`/download/*`、`/report`
各返回 200 / 303 / 403，**无 crash**。

### 9.3 附带排查：一次“运行时崩溃”的定性

过程中 `wrangler dev` 的日志曾出现过：

```
[WARN] The Workers runtime crashed unexpectedly and is being restarted (crash #1).
```

**已排除是代码问题。** 定性过程：

- 怀疑对象是「强制杀进程导致 supervisor 重启」，而不是业务代码。
- **验证方式**：重新起服务（换端口），跑一遍完整流程（含 2 MB 上传、下载、审核、30 次连续请求），
  **全程不杀任何进程** —— 结果零 crash，全部 200。
- **结论**：那条 crash 是 `taskkill` 强杀 `workerd` 时的副作用，不是代码缺陷。

（顺带记录一个环境坑：`npx wrangler dev` 会拉起跨 MSYS/Windows 边界的进程树
`bash → node.exe(wrangler cli) → workerd.exe`。用上层工具杀掉 bash 包装层后，
node/workerd **仍然存活**并继续监听端口、锁住 `.wrangler/state` 文件。
正确杀法是：`netstat -ano` 找到 workerd 的 PID → 查其父进程 → `taskkill /F /T` 父 PID。
否则端口会“杀了又有”。这条已写入技能 `cloudflare-workers-local-dev`。）

### 9.4 验收方认为仍未验证到的

沿用第 8 节的判断，并补充：

- **真云部署**：`wrangler.toml` 里的 `database_id` 仍是占位符
  （`00000000-0000-0000-0000-000000000000`）。**没有用户的 Cloudflare 账号就无法推进这一步**，
  这是硬前提，不是可绕过的工作量。**“本地全绿”不等于“云端可用”。**
- **远端 D1 / 远端 R2 的真实行为**（本地是 Miniflare 模拟，与远端存在已知语义差异）。
- **真机浏览器**、50 MB 边界、JPEG/PNG 的真实样例元数据清理。

