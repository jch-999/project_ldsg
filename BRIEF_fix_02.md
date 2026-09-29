# 修复交底书 · 第 2 期

## 任务

修复一个已复现的严重缺陷：**一个中途断开的请求会把整个服务卡死，所有用户都无法访问。**

## 缺陷现象（已实测复现）

一个客户端发起上传请求，声明 `Content-Length` 为 47.5MB，实际只发送约 5MB 后就断开连接。之后：

- 服务**完全停止响应**，任何后续请求（包括首页 `GET /`）都超时，持续至少 30 秒无恢复
- 服务端日志抛出 `Traceback`，最后停在 `app.py` 的 `send_html()` → `end_headers()` 处
- 数据库没有脏记录、磁盘没有残留文件（这两项是好的，不用改）

复现脚本（本机已验证可稳定复现）：
```
C:\Users\jch\AppData\Local\Temp\hermes-verify-hang.py
```
运行方式：`python hermes-verify-hang.py`
它会起服务、发一个半截请求、然后在 1s/5s/15s/30s 四个时间点探测服务是否还活着。
当前结果：四个时间点全部无响应。

**注意一个脚本自身的行为**（已知，不要去修它）：脚本末尾要关掉服务、读出服务端日志。
服务卡死时，`proc.terminate()` 之后的读日志动作自己也会被拖住几秒——脚本里已经用硬超时处理了，
最坏情况它会多花约 10 秒才打印日志。**这是脚本正常的收尾行为，不是被测服务的缺陷，也不代表服务已经好或没好。**
判断修复是否成功只看那四个时间点的探测结果。

## 根因分析（已定位到行）

### 问题一：读请求体时没有任何超时

`app.py` 第 177-186 行：

```python
def read_body(self, length):
    chunks = []
    remaining = length
    while remaining > 0:
        chunk = self.rfile.read(min(65536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)
```

这段逻辑本身没错，但 `self.rfile` 底层的 socket 没有设置超时。当客户端声明 47.5MB 却只发 5MB 后消失，`self.rfile.read()` 会一直阻塞等待剩余的 42.5MB，**没有上限**。

在 Windows 上，客户端硬关闭连接（SO_LINGER=0 发出 RST）时，这个 RST 不一定会让阻塞中的 `read` 立刻返回。

### 问题二：异常处理试图往一个已经死掉的连接写响应

`app.py` 第 264-274 行：

```python
def do_POST(self):
    try:
        self.route_post()
    except Exception as exc:
        self.log_message("处理出错: %r", exc)
        traceback.print_exc()
        self.send_html(500, pages.render_message(
            "服务器出错了",
            "处理这个请求时发生错误：%s" % exc,
            [("/", "回到首页")],
        ))
```

当读请求体失败抛出异常后，这里会尝试 `send_html(500, ...)`。但此时连接已经废了，写响应会在 `end_headers()`（第 168 行）或 `self.wfile.write()`（第 169 行）**再次阻塞**。日志证实了这一点——traceback 的最后一帧就是 `send_html` 里的 `end_headers()`。

### 问题三：没有兜底

`app.py` 第 783 行创建服务器时没有任何超时配置：

```python
server = ThreadingHTTPServer((cfg["host"], candidate), Handler)
```

`ThreadingHTTPServer` 会为每个连接开一个线程。如果这些线程被阻塞的读写卡住，它们不会释放。多来几个半截请求，线程就被耗尽，服务对所有人失去响应。

## 修复要求

**目标：一个中途断开的请求，只影响它自己，不影响其他任何人。**

请按下面三条改，也可以提出更好的方案，但必须覆盖这三条：

1. **给每个连接的 socket 设置超时。** 让阻塞的 `read` / `write` 能在有限时间内失败，而不是无限等待。
   建议在 handler 里做（例如覆写 `setup()`，或给 `self.connection` / `self.rfile` 设超时）。
   超时值要合理：正常上传 47.5MB 在本机只需约 1.3 秒，即使慢速网络也应留足余量。请选择一个既能兜住卡死、又不会误杀正常上传的值，并在注释里说明你的取值理由。

2. **读请求体失败后，不要试图在同一个连接上写响应。** 应该记录日志（可以用 `log_message`）然后直接放弃这个请求——例如设置 `self.close_connection = True` 并直接返回，不要调用 `send_html`。

3. **确认一个失败不会影响后续请求。** 服务必须继续正常处理其他连接。

## 必须遵守的约束

- 不要引入任何第三方库（这个项目零依赖是硬要求）。
- 不要改动数据库 schema，不要改动任何页面的 HTML 或 CSS。
- 不要动 `metadata.py`。
- 不要重建已实现的功能，只修这个缺陷。
- 如果发现读请求体失败时应该返回给用户某种提示，注意：**此时连接已断，用户收不到任何东西**，这是正常且无法避免的，不要为此引入复杂机制。

## 工作方式（重要，请照做）

1. **只做修复，不做研究。** 根因已经在上文定位到行，不需要你再重新分析一遍。
2. **先复现一次就够。** 跑 `hermes-verify-hang.py` 确认现状（四个时间点全部无响应）之后，立刻开始改代码。
   **不要为了搞清"为什么脚本会卡住"去写新的测试脚本**——复现脚本自身的收尾阻塞是已知的、已处理的行为（见上文），不是你要解决的问题。
3. **不要自己写额外的测试脚本。** 下面已经给了三个现成脚本，改完直接跑它们。若你自写的脚本卡住，那是你的脚本问题，不是项目问题。
4. 单个复现脚本的运行时间上限是 **5 分钟**。如果你发现某个命令跑超过 5 分钟还没返回，**立刻放弃它**，继续往下做，并在交付说明里注明"该命令超时未返回"。
5. 若某个复测脚本的结果与预期不符，**如实报告实际输出，不要为了让它变绿而反复重跑或修改脚本**。跑不通就说明跑不通。

## 交付要求

1. 改完的代码
2. 更新 `SELF_TEST.md`：新增一节记录这次修复，包含
   - 你实际执行过的命令和**真实输出**
   - 用 `hermes-verify-hang.py` 复测的结果（四个时间点是否都恢复正常）
   - 重新跑 `hermes-verify-upload-suite.py` 的结果
   - 明确列出你认为没验证到的地方

## 复测脚本位置（都在本机，可直接运行）

- `C:\Users\jch\AppData\Local\Temp\hermes-verify-hang.py` — 卡死复现（专项）
- `C:\Users\jch\AppData\Local\Temp\hermes-verify-upload-suite.py` — 上传鲁棒性全量（24 项，当前 22 通过 / 2 失败）
- `C:\Users\jch\AppData\Local\Temp\hermes-verify-frontend.py` — 浏览器前端校验

要求：跑完后，hang 脚本的四个时间点必须全部"正常"，upload-suite 必须 24 项全通过。
