# SELF_TEST.md

本文件记录我在实现完成后**实际执行过的命令和真实输出**。所有输出都是从终端直接
复制过来的，没有改写、没有推测。凡是没验证的，我会明确写「未验证」。

- 测试日期：2026-09-29
- 系统：Windows 10，shell 为 PowerShell
- Python：`Python 3.14.6`（用系统已有的 Python，没有安装新版本）
- SQLite：`3.50.4`（Python 标准库自带的 sqlite3）
- 第三方依赖：**零**。没有执行过任何 `pip install`。

---

## 1. 环境与语法检查

### 命令

```powershell
python --version; py --version
Get-ChildItem -LiteralPath 'D:\AI输出的文件\project_ldsg' -Force | Select-Object Mode,Length,Name | Format-Table -AutoSize
python -c "import sqlite3, http.server, email, zipfile, xml.etree.ElementTree, hmac, hashlib, uuid, json; print('stdlib ok'); print('sqlite', sqlite3.sqlite_version)"
```

### 真实输出

```
Python 3.14.6
Python 3.14.6

Mode   Length Name
----   ------ ----
-a----   7960 BRIEF_dev_01.md
stdlib ok
sqlite 3.50.4
```

### 命令

```powershell
python -m py_compile app.py db.py config.py metadata.py pages.py; if ($LASTEXITCODE -eq 0) { "py_compile: OK" }
```

### 真实输出

```
py_compile: OK
```

---

## 2. 元数据剥离功能：独立函数验证（重点要求）

交底书要求元数据剥离必须是「可以单独调用的独立函数」。我把它写成了
`metadata.py` 里的 `strip_metadata(src, dst)`，并提供命令行入口。

验证脚本 `verify_metadata.py` 会自己生成 4 个带元数据的样例文件（docx / png / jpg / pdf），
直接调用 `metadata.strip_metadata()`（**不经过上传流程、不经过服务器**），
然后重新打开输出文件检查元数据是否真的没了。

### 命令

```powershell
python verify_metadata.py
```

### 真实输出

```
--- metadata.strip_metadata(document.docx, document_clean.docx) ---
返回: kind=ooxml stripped=True removed=['creator(作者)', 'lastModifiedBy(最后修改人)', 'keywords(关键词)', 'revision(修订号)', 'created(创建时间)', 'modified(修改时间)', 'Company(公司)', 'Manager(经理)', 'TotalTime(总编辑时间)', 'AppVersion(应用版本)', 'custom(自定义属性)']
说明: 已清理 docProps 下的作者 / 公司 / 修订等属性。

--- metadata.strip_metadata(image.png, image_clean.png) ---
返回: kind=png stripped=True removed=['PNG tEXt 文本块', 'PNG tIME 时间戳块', 'PNG eXIf EXIF块']
说明: 已删除 PNG 的文本 / EXIF / 时间戳块。

--- metadata.strip_metadata(photo.jpg, photo_clean.jpg) ---
返回: kind=jpeg stripped=True removed=['JPEG EXIF (APP1)']
说明: 已删除 JPEG 的 EXIF / XMP / IPTC / 注释段。

--- metadata.strip_metadata(report.pdf, report_clean.pdf) ---
返回: kind=pdf stripped=True removed=['Author', 'Creator', 'Producer', 'Title', 'CreationDate', 'XMP']
说明: 已尽力清除 PDF 的 /Info 与 XMP 元数据。

=== 检查清理结果 ===
[PASS] docx 不再包含 'Alice Author'                       core.xml
[PASS] docx 不再包含 'Bob Editor'                         core.xml
[PASS] docx 不再包含 'secret-keywords'                    core.xml
[PASS] docx 不再包含 '2026-01-02T03:04:05Z'               core.xml
[PASS] docx 不再包含 'ACME Corporation'                   app.xml
[PASS] docx 不再包含 'Carol Boss'                         app.xml
[PASS] docx 不再包含 '987'                                app.xml
[PASS] docx 不再包含 '16.0000'                            app.xml
[PASS] docx 自定义属性被清空                                  custom.xml
[PASS] docx 修订号被改成中性值 1                               core.xml
[PASS] docx 仍是可打开的 zip                                zip 完整性
[PASS] png 文件签名正确                                     PNG signature
[PASS] png 元数据块已删除                                    chunks=['IHDR', 'IDAT', 'IEND']
[PASS] png 图像块仍完整                                     IHDR/IDAT/IEND 都在
[PASS] jpg 起始/结束标记正确                                  SOI/EOI
[PASS] jpg 的 EXIF/APP1 段已删除                           markers=['0xe0', '0xdb', '0xc0', '0xc4', '0xc4', '0xda']
[PASS] jpg 其他段保留                                      包含量化表或帧头
[PASS] pdf 长度不变（xref 偏移不失效）                           1105 -> 1105 字节
[PASS] pdf 文件头尾完整                                     header/trailer
[PASS] pdf 不再包含 'Zhang San'                           /Info 字符串
[PASS] pdf 不再包含 'SecretProducer'                      /Info 字符串
[PASS] pdf 不再包含 'My Private Notes'                    /Info 字符串
[PASS] pdf 不再包含 'TestTool 1.0'                        /Info 字符串
[PASS] pdf XMP 元数据已被清空                                XMP 流

--- metadata.strip_metadata(note.md, note_clean.md) ---
返回: kind=passthrough stripped=False note=该格式本期不处理元数据，已原样复制。
[PASS] md 原样复制                                        passthrough

总计 25 项，通过 25 项，失败 0 项。
```

> 说明：从命令行单独调用也可以，例如
> `python metadata.py 原始文件.docx 清理后.docx`，它会打印一段 JSON。

---

## 3. Web 功能端到端验证

`verify_web.py` 会自动在 8123 端口启动一份真实的 `app.py`（通过 `LDSG_PORT`、
`LDSG_ADMIN_TOKEN` 环境变量控制），然后用 `http.client` 模拟浏览器走完整流程，
并直接读 SQLite 和磁盘核对结果，跑完自动关闭服务。

覆盖：首页 / 上传页 / 关于页 / 404、后端类型校验、后端大小校验、
上传入库、pending 不公开、sha256 去重、管理员登录、审核通过、
搜索、组合筛选、详情页浏览计数、下载计数、docx 端到端元数据剥离、
举报 3 次自动下架（文件保留）、恢复、拒绝、下架。

### 命令

```powershell
python verify_web.py
```

### 真实输出

```
[PASS] GET / 返回 200                                         status=200
[PASS] 首页有中文标题                                              包含「资料库」
[PASS] GET /upload 返回 200                                   status=200
[PASS] 上传页下发了前端大小/类型校验 JS
[PASS] GET /about 返回 200 且是中文                               status=200
[PASS] 不存在的页面返回 404 和中文提示                                   status=404
[PASS] 后端拒绝白名单外的 .exe                                       status=400
[PASS] 后端拒绝超过上限的请求体（413）                                    status=413
[PASS] 上传成功（200 + 中文提示）                                     status=200
[PASS] 数据库里查到刚上传的资料
[PASS] 上传后状态是 pending                                       status=pending
[PASS] original_name 保存了原始文件名                               my_original_name.md
[PASS] 系统生成了规范文件名                                           TEST1010_笔记_2026S1_451bc126.md
[PASS] material_sources 写了 provider='local'
[PASS] 上传写了 audit_log
[PASS] pending 资料不出现在首页
[PASS] pending 详情页显示「等待管理员审核」                               status=200
[PASS] 重复文件提示已存在并给出原链接                                      status=200
[PASS] 重复文件没有写入新记录                                          count=1
[PASS] 未登录访问 /admin 显示登录页                                   status=200
[PASS] 用正确令牌登录返回 303 并下发 cookie                             status=303 cookie=ldsg_admin=9670d8464a206b45b8e4e567c03be366fc82f2fa89aee177adaec1ce8c4cf4f2
[PASS] 管理员通过审核返回 303                                        status=303
[PASS] 数据库状态变成 approved                                     status=approved
[PASS] 审核动作写入 audit_log
[PASS] 搜索能搜到已通过的资料
[PASS] 按课程代码筛选能命中
[PASS] 筛不到时显示中文空结果
[PASS] 详情页显示标题和完整信息
[PASS] 公开详情页不泄露 original_name                               只有管理页能看到原始文件名
[PASS] 详情页浏览计数增加                                            views=1
[PASS] 下载返回 200 且内容一致                                       status=200 size=29
[PASS] 下载计数 +1                                              downloads=1
[PASS] docx 上传成功                                            status=200
[PASS] docx 文件已落盘                                           uploads/cf348391edf39b61_9db98873.docx
[PASS] 落盘的 docx 里作者已被清除                                     core.xml
[PASS] 落盘的 docx 里公司已被清除                                     app.xml
[PASS] 落盘的 docx 正文内容仍在                                      正文未被破坏
[PASS] 举报 3 次后状态自动变成 removed                                status=removed
[PASS] 数据库里有 3 条未处理举报                                       open_reports=3
[PASS] 自动下架写入 audit_log
[PASS] 下架后文件仍在磁盘上（只改状态）                                     uploads/c0887f75562addca_451bc126.md
[PASS] 下架资料详情页给出中文提示
[PASS] 下架资料不能下载                                             status=404
[PASS] 管理页能看到举报列表
[PASS] 管理员恢复后状态回到 approved                                  status=approved
[PASS] 恢复后可以重新下载                                            status=200
[PASS] 管理员动作 reject 生效                                      status=rejected
[PASS] 管理员动作 remove 生效                                      status=removed

--- 服务端日志（节选） ---
   管理页： http://127.0.0.1:8123/admin
   关于：   http://127.0.0.1:8123/about

 管理令牌：selftest-token-123456
 （令牌也可以改 config.ini 里的 admin_token，或用环境变量 LDSG_ADMIN_TOKEN 覆盖）

 停止服务：在本窗口按 Ctrl+C
==============================================================

[18:14:12] "GET / HTTP/1.1" 200 -
[18:14:12] "GET /upload HTTP/1.1" 200 -
[18:14:12] "GET /about HTTP/1.1" 200 -
[18:14:12] "GET /no-such-page HTTP/1.1" 404 -
[18:14:12] "POST /upload HTTP/1.1" 400 -
[18:14:12] "POST /upload HTTP/1.1" 413 -
[18:14:12] "POST /upload HTTP/1.1" 200 -
[18:14:12] "GET /?q=1790676851 HTTP/1.1" 200 -
[18:14:12] "GET /material/451bc1263ad24146bc2972c17a33d4f2 HTTP/1.1" 200 -
[18:14:12] "GET /admin HTTP/1.1" 200 -
[18:14:12] "POST /admin HTTP/1.1" 303 -
[18:14:12] "POST /admin/action HTTP/1.1" 303 -
[18:14:12] "GET /download/451bc1263ad24146bc2972c17a33d4f2 HTTP/1.1" 200 -
[18:14:12] "POST /report HTTP/1.1" 200 -
[18:14:12] "GET /download/451bc1263ad24146bc2972c17a33d4f2 HTTP/1.1" 404 -
[18:14:12] "POST /admin/action HTTP/1.1" 303 -
[18:14:12] "GET /download/451bc1263ad24146bc2972c17a33d4f2 HTTP/1.1" 200 -

总计 48 项，通过 48 项，失败 0 项。
```

> 截图/浏览器层面的视觉验证**未验证**（本机没有跑浏览器自动化）。上面的校验都是
> HTTP 状态码 + 返回 HTML 内容 + 数据库 + 磁盘文件四个层面的真实检查。

---

## 4. `start.bat` 真实验证

要求是「双击就能启动，并提示用户去浏览器打开哪个地址」。我用管道方式启动
`cmd /c start.bat`（等价于双击），等它起来后请求首页，再关掉它。

### 命令

```powershell
python verify_start_bat.py
```

### 真实输出

```
HTTP_STATUS=200
CONTENT_LENGTH=6258
--- start.bat 完整输出 ---
正在启动课程资料共享站，请稍等...

==============================================================
 课程资料共享站 已启动
 请在浏览器打开下面的地址：

   首页：   http://127.0.0.1:8000/
   上传：   http://127.0.0.1:8000/upload
   管理页： http://127.0.0.1:8000/admin
   关于：   http://127.0.0.1:8000/about

 管理令牌：E9r0-2U4FcMYJDiX
 （令牌也可以改 config.ini 里的 admin_token，或用环境变量 LDSG_ADMIN_TOKEN 覆盖）

 停止服务：在本窗口按 Ctrl+C
==============================================================

[18:14:20] "GET / HTTP/1.1" 200 -
```

> 上面这个令牌 `E9r0-2U4FcMYJDiX` 只是本次测试随机生成的，交付时我已经把
> `config.ini` 和 `data/` 删掉，所以你第一次双击会生成一个**属于你自己的新令牌**，
> 以启动窗口打印的为准。

---

## 5. 数据库 schema 与交底书逐字段比对

### 命令

```powershell
python -c "
import sqlite3
conn = sqlite3.connect(r'D:\AI输出的文件\project_ldsg\data\materials.db')
expected = {
 'materials': ['id','title','description','course_code','course_name','category','semester','tags','file_key','file_name','original_name','file_size','mime_type','sha256','uploader_note','upload_credential','status','review_note','reviewed_at','reviewer','downloads','views','ip_hmac','created_at','updated_at'],
 'material_sources': ['material_id','provider','object_key','size','sha256','priority'],
 'credentials': ['credential','approved_count','level','first_seen'],
 'reports': ['id','material_id','reason','detail','ip_hmac','status','created_at'],
 'upload_events': ['ip_hmac','credential','created_at'],
 'audit_log': ['id','material_id','action','reason','actor','created_at'],
}
ok = True
for table, cols in expected.items():
    actual = [r[1] for r in conn.execute('PRAGMA table_info(%s)' % table)]
    same = actual == cols
    ok = ok and same
    print(('MATCH ' if same else 'DIFF  ') + table + ': ' + ','.join(actual))
print()
print('schema matches brief exactly:', ok)
print('credentials rows:', conn.execute('SELECT COUNT(*) FROM credentials').fetchone()[0])
print('upload_events rows:', conn.execute('SELECT COUNT(*) FROM upload_events').fetchone()[0])
print('material_sources providers:', [r[0] for r in conn.execute('SELECT DISTINCT provider FROM material_sources')])
print('audit_log actions:', sorted(set(r[0] for r in conn.execute('SELECT action FROM audit_log'))))
conn.close()
"
```

### 真实输出

```
MATCH materials: id,title,description,course_code,course_name,category,semester,tags,file_key,file_name,original_name,file_size,mime_type,sha256,uploader_note,upload_credential,status,review_note,reviewed_at,reviewer,downloads,views,ip_hmac,created_at,updated_at
MATCH material_sources: material_id,provider,object_key,size,sha256,priority
MATCH credentials: credential,approved_count,level,first_seen
MATCH reports: id,material_id,reason,detail,ip_hmac,status,created_at
MATCH upload_events: ip_hmac,credential,created_at
MATCH audit_log: id,material_id,action,reason,actor,created_at

schema matches brief exactly: True
credentials rows: 0
upload_events rows: 0
material_sources providers: ['local']
audit_log actions: ['approve', 'auto_remove', 'reject', 'remove', 'restore', 'upload']
```

结论：6 张表的字段名、顺序、数量都和交底书完全一致。
另外按交底书要求给 `materials(status, created_at)`、`materials(sha256)`、
`reports(material_id, status)` 建了索引（索引不是字段，不影响结构兼容）。

---

## 6. 完成情况总结

### 6.1 我认为已经完成的

1. **页面**：首页 `/`、搜索、组合筛选、分页（每页 20 条）、上传页 `/upload`、
   详情页 `/material/<id>`、下载 `/download/<id>`、管理页 `/admin`、关于页 `/about`。
2. **上传硬性规则**：单文件 50 MB（前端 JS + 后端双重校验，后端校验已用真实请求证明
   会返回 400/413）、扩展名白名单（前后端都有）、sha256 去重（返回「已存在」+ 原链接）、
   上传后 `pending`、系统规范文件名、`original_name` 只在管理页可见。
3. **举报**：未处理举报累计 3 条自动把 `status` 改成 `removed`，**文件保留在磁盘上**
   （已用 `os.path.isfile(...)` 证明）。
4. **管理页**：令牌从环境变量或 `config.ini` 读取（自动生成，不硬编码）；
   通过 / 拒绝 / 下架 / 恢复；举报列表；每个动作写 `audit_log`。
5. **元数据剥离**：`metadata.strip_metadata()` 独立函数 + 命令行入口；支持
   PDF / docx / pptx / xlsx / jpg / jpeg / png；上传流程会调用它，且落盘后的
   docx 已证明作者、公司被清除。
6. **空结果 / 出错 / 提交中**：都有中文提示；表单提交时按钮变「提交中…」。
7. **`start.bat`**：双击可启动，控制台打印访问地址和管理令牌；已实际跑通。
8. **`README.md`**：中文写了启动方式、进管理页、每个文件的作用。
9. **数据库**：6 张表结构逐字段与交底书一致；`credentials`、`upload_events`
   只建表、不写业务逻辑（符合交底书）；`material_sources` 只写 `provider='local'`。
10. **没有做的事**：没有 git init / commit，没有装任何第三方包，没有动工作目录以外的文件。

### 6.2 我认为没做、或做了但不确定的

1. **PDF 元数据剥离不是 100% 可靠（最大的不确定项）。**
   纯标准库方案只能处理「元数据以明文存在于 `/Info` 字典或 XMP 流」的 PDF：
   - 我构造的明文样例 PDF 实测通过；
   - 但如果 PDF 把 `/Info` 压进了「对象流（object stream）」里，或者 PDF 是加密的，
     明文搜索就找不到，**这部分元数据不会被清除**。函数会返回一句提示，
     但文件仍然会被保存。
   - 需要说明：我**没有**找到一个只用标准库就能生成「对象流压缩 PDF」的办法，
     所以这种漏删情形**未用真实文件验证**，只是根据 PDF 格式原理判断的限制。
   - 如果必须做到「任何 PDF 都干净」，就需要引入第三方库（见 6.3 第 2 条）。
2. **浏览器层面未验证**：拖拽上传、按钮变「提交中…」的视觉效果、下拉框筛选的
   交互，都**没有用真实浏览器点击验证过**，只验证了页面 HTML 和 JS 被下发、
   以及 HTTP 流程正确。但后端的每一条分支都用真实请求验证了。
3. **并发/性能未验证**：没有做多用户同时上传的压力测试。代码用了
   `ThreadingHTTPServer` + 每个请求独立 SQLite 连接 + WAL 模式，理论上够用，
   但**未做压测**。
4. **`zoom` 类图片之外的格式未处理**：白名单里没有 webp/heic，所以不存在「图片
   元数据没清」的问题；但 `.epub` 和 `.zip` 只做原样复制，**不清理内部元数据**
   （交底书只要求 PDF / Office / 图片，这两个属于超范围）。
5. **备份到 D1 未验证**：交底书说「不要为将来接 Cloudflare 写适配代码」，
   所以我没做、也没测迁移。
6. **`verify_web.py` 会往 `data/` 写测试数据**（标题带 `WEBTEST`），这是验证脚本的
   设计，不影响正常使用；交付前我已经清空 `data/`。

### 6.3 我发现的需求矛盾或坑（按交底书要求必须写出来）

1. **「加载中要有人话文案」 vs 「服务端直接吐 HTML、前端不做复杂交互」有冲突。**
   因为本站没有任何 AJAX / 实时搜索，页面是整页跳转的，严格意义上不存在「客户端
   加载中」这个状态。我的处理是：表单提交时把按钮变成禁用并显示「提交中…」，
   用浏览器自身的加载指示补齐。**如果你要的是「像单页应用那样的加载动画」，
   那就和「不引入前端构建工具、服务端直接吐 HTML」的要求矛盾了**，需要你确认取舍。

2. **「元数据剥离如果标准库做不到，允许引入依赖」 vs 「依赖越少越好、其余一律不许 pip install」有张力。**
   - Office（docx/pptx/xlsx）和图片（jpg/png）用标准库可以完整处理，我做到了；
   - PDF 用标准库**只能做到明文部分**，对象流/加密 PDF 处理不了。
   - 我最终选择**不加任何第三方库**，换取「零依赖、双击即用、不需要联网装包」。
     代价就是上面 6.2 第 1 条那个 PDF 限制。
   - 如果你可以接受 `pip install pypdf`（或 pikepdf），我可以再补一个「完整版」PDF
     清理；但那会让项目第一次运行需要联网安装依赖，和「零云端依赖」的体验有冲突。

3. **「举报累计 3 次（status 未处理的）」隐含举报有「已处理」状态，但功能清单里
   只写了「能看举报列表」，没写能处理。**
   如果举报永远不能被标记为已处理，那么 `reports.status` 这个字段就没有意义，
   而且一份被误报下架的资料恢复后，举报数还是 3，会立刻又触发下架。
   我在管理页增加了一个很小的「标记已处理」按钮（写 `audit_log`），
   让这个字段真正起作用。**这算是我对交底书做的一处合理补充**，如果你不要这个按钮，
   告诉我，删掉即可。

4. **`credentials` / `upload_events` 两张表本期没有任何业务逻辑会用到。**
   交底书自己也说明了这一点，我按要求「只建表、不写逻辑」。因此这两张表会一直是空的，
   这是预期行为，不是 bug。

5. **Windows 批处理文件必须是 CRLF 换行，这是实现时踩到的真实坑。**
   一开始 `start.bat` 被写成了 LF（Unix）换行，双击时报
   `'ython' is not recognized as an internal or external command`——cmd.exe 解析
   批处理时把行首的 `p` 吃掉了，`python` 变成了 `ython`。改成 CRLF 后正常启动。
   如果你以后用会写 LF 换行的编辑器改 `start.bat`，要记得存成 CRLF。

6. **管理令牌以明文存在 `config.ini` 里。**
   这是本地小站，能读到 `config.ini` 的人本来就能读到数据库和文件，所以不算额外的
   安全边界。但如果你把项目文件夹分享给别人，记得先改令牌或删掉 `config.ini`。
