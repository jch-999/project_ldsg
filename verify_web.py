"""
Web 功能 · 手工验证脚本
======================

不是测试框架，是一条可反复执行的验证命令：

    python verify_web.py

它会自动：
    1. 用 8123 端口启动一份 app.py；
    2. 用 http.client 模拟浏览器，走完这些流程：
       首页 → 上传（类型校验 / 大小校验 / 去重）→ 待审核 →
       管理员登录 → 通过 → 搜索筛选 → 下载 → 举报 3 次自动下架 →
       恢复 → 关于页 / 404 页；
    3. 直接读数据库和磁盘，确认状态和文件确实符合预期；
    4. 打印 PASS / FAIL 并关掉服务。

注意：它会在 data/ 里留下测试数据（标题带 WEBTEST 字样），方便你肉眼检查。
跑完想清空，关掉程序后删掉 data/ 文件夹即可。
"""

import http.client
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import zipfile

import verify_metadata


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOST = "127.0.0.1"
PORT = 8123
TOKEN = "selftest-token-123456"

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, ok))
    print("[%s] %-52s %s" % ("PASS" if ok else "FAIL", name, detail))


def query_one(sql, params=()):
    conn = sqlite3.connect(os.path.join(BASE_DIR, "data", "materials.db"), timeout=10)
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(sql, params).fetchone()
    finally:
        conn.close()


def multipart_body(fields, file_field, file_name, file_bytes):
    boundary = "----selftestboundary1234567890"
    parts = []
    for key, value in fields.items():
        parts.append(("--%s\r\n" % boundary).encode())
        parts.append(('Content-Disposition: form-data; name="%s"\r\n\r\n' % key).encode())
        parts.append(value.encode("utf-8") + b"\r\n")
    parts.append(("--%s\r\n" % boundary).encode())
    parts.append(
        ('Content-Disposition: form-data; name="%s"; filename="%s"\r\n'
         'Content-Type: application/octet-stream\r\n\r\n' % (file_field, file_name)).encode()
    )
    parts.append(file_bytes + b"\r\n")
    parts.append(("--%s--\r\n" % boundary).encode())
    return b"".join(parts), "multipart/form-data; boundary=%s" % boundary


class Client:
    """极简 HTTP 客户端，手动管理 cookie，方便检查 303 状态码。"""

    def __init__(self, host, port):
        self.conn = http.client.HTTPConnection(host, port, timeout=30)
        self.cookie = None

    def request(self, method, path, body=None, content_type=None, extra_headers=None):
        headers = {}
        if content_type:
            headers["Content-Type"] = content_type
        if body is not None:
            headers["Content-Length"] = str(len(body))
        if self.cookie:
            headers["Cookie"] = self.cookie
        if extra_headers:
            headers.update(extra_headers)
        self.conn.request(method, path, body=body, headers=headers)
        response = self.conn.getresponse()
        data = response.read()
        set_cookie = response.getheader("Set-Cookie")
        if set_cookie:
            self.cookie = set_cookie.split(";")[0]
        return response.status, data


def wait_for_server(process, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        try:
            conn = http.client.HTTPConnection(HOST, PORT, timeout=2)
            conn.request("GET", "/")
            conn.getresponse().read()
            conn.close()
            return True
        except OSError:
            time.sleep(0.25)
    return False


def make_unique_docx(path, marker):
    """造一个带元数据、内容唯一的 docx，避免和上次运行的 sha256 撞车。"""
    verify_metadata.make_docx(path)
    with zipfile.ZipFile(path) as zin:
        items = {name: zin.read(name) for name in zin.namelist()}
    items["word/document.xml"] = items["word/document.xml"].replace(b"Hello", marker.encode("ascii"))
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name, value in items.items():
            zout.writestr(name, value)


def main():
    data_dir = os.path.join(BASE_DIR, "data")
    os.makedirs(data_dir, exist_ok=True)
    marker = str(int(time.time()))
    work_dir = os.path.join(BASE_DIR, "selftest_tmp")
    os.makedirs(work_dir, exist_ok=True)

    env = dict(os.environ)
    env["LDSG_PORT"] = str(PORT)
    env["LDSG_ADMIN_TOKEN"] = TOKEN

    process = subprocess.Popen(
        [sys.executable, os.path.join(BASE_DIR, "app.py")],
        cwd=BASE_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        if not wait_for_server(process):
            print("服务没有在 15 秒内启动。")
            print(process.stdout.read().decode("utf-8", "replace"))
            return 1

        client = Client(HOST, PORT)

        # ---- 1. 基本页面 ----
        status, body = client.request("GET", "/")
        check("GET / 返回 200", status == 200, "status=%d" % status)
        check("首页有中文标题", "资料库".encode("utf-8") in body, "包含「资料库」")

        status, body = client.request("GET", "/upload")
        check("GET /upload 返回 200", status == 200, "status=%d" % status)
        check("上传页下发了前端大小/类型校验 JS",
              b"maxBytes" in body and b"allowed.indexOf" in body and b"50 * 1024 * 1024" in body, "")

        status, body = client.request("GET", "/about")
        # 判据查的是 BRIEF 的实质要求（版权说明 + 投诉通道），不查某一版的具体措辞——
        # 页面文案会演进，锁死字符串会让「功能好的」被误报成 FAIL。
        about_text = body.decode("utf-8", "replace")
        check("GET /about 返回 200 且含免责/版权与投诉两节",
              status == 200 and "非官方声明" in about_text and "投诉" in about_text
              and "著作权" in about_text,
              "status=%d" % status)

        # ---- 1b. 版权区必须带 /about 链接（语义判据，不看引号风格）----
        # 判据只认「这个 href 指向 /about」这件事本身，不管源码用单引号还是双引号。
        status, body = client.request("GET", "/")
        html = body.decode("utf-8", "replace")
        footer = html[html.rfind("<footer"):html.rfind("</footer>") + 9] if "<footer" in html else ""
        about_hrefs = re.findall(r'href\s*=\s*["\'](/about)["\']', footer)
        check("首页版权区含指向 /about 的链接", bool(about_hrefs), "footer 片段=%r" % footer[:120])

        status, body = client.request("GET", "/no-such-page")
        check("不存在的页面返回 404 和中文提示", status == 404 and "页面不存在".encode("utf-8") in body, "status=%d" % status)

        # ---- 2. 类型白名单：后端拒绝 .exe ----
        body_data, ctype = multipart_body(
            {"title": "WEBTEST 非法类型"}, "file", "virus.exe", b"MZ fake executable"
        )
        status, body = client.request("POST", "/upload", body_data, ctype)
        check("后端拒绝白名单外的 .exe", status == 400 and "不支持的文件类型".encode("utf-8") in body, "status=%d" % status)

        # ---- 3. 大小校验：声明一个超过 52MB 的请求体 ----
        big = http.client.HTTPConnection(HOST, PORT, timeout=10)
        big.putrequest("POST", "/upload")
        big.putheader("Content-Type", "multipart/form-data; boundary=xx")
        big.putheader("Content-Length", str(60 * 1024 * 1024))
        big.endheaders()
        big_response = big.getresponse()
        big_body = big_response.read()
        big.close()
        check("后端拒绝超过上限的请求体（413）",
              big_response.status == 413 and "50 MB".encode("utf-8") in big_body,
              "status=%d" % big_response.status)

        # ---- 4. 正常上传一个 md（内容唯一，避免去重） ----
        md_path = os.path.join(work_dir, "webtest_%s.md" % marker)
        md_bytes = ("# web test\nmarker=%s\n" % marker).encode("utf-8")
        with open(md_path, "wb") as f:
            f.write(md_bytes)
        title = "WEBTEST 自动测试 %s" % marker
        body_data, ctype = multipart_body(
            {
                "title": title,
                "course_code": "TEST1010",
                "course_name": "自动化测试课",
                "category": "笔记",
                "semester": "2026S1",
                "tags": "测试,自动",
                "description": "这是 verify_web.py 生成的测试资料",
                "uploader_note": "selftest",
            },
            "file", "my_original_name.md", md_bytes,
        )
        status, body = client.request("POST", "/upload", body_data, ctype)
        check("上传成功（200 + 中文提示）",
              status == 200 and "上传成功".encode("utf-8") in body, "status=%d" % status)

        material = query_one("SELECT * FROM materials WHERE title = ?", (title,))
        check("数据库里查到刚上传的资料", material is not None, "")
        if material is None:
            return 1
        material_id = material["id"]
        check("上传后状态是 pending", material["status"] == "pending", "status=%s" % material["status"])
        check("original_name 保存了原始文件名", material["original_name"] == "my_original_name.md", material["original_name"])
        check("系统生成了规范文件名", material["file_name"].startswith("TEST1010_笔记_2026S1_"), material["file_name"])
        source = query_one("SELECT * FROM material_sources WHERE material_id = ?", (material_id,))
        check("material_sources 写了 provider='local'", source is not None and source["provider"] == "local", "")
        audit = query_one("SELECT * FROM audit_log WHERE material_id = ? AND action = 'upload'", (material_id,))
        check("上传写了 audit_log", audit is not None, "")

        # ---- 5. pending 不出现在首页，详情页给中文提示 ----
        status, body = client.request("GET", "/?q=%s" % marker)
        check("pending 资料不出现在首页", title.encode("utf-8") not in body, "")
        status, body = client.request("GET", "/material/%s" % material_id)
        check("pending 详情页显示「等待管理员审核」",
              status == 200 and "等待管理员审核".encode("utf-8") in body, "status=%d" % status)

        # ---- 6. sha256 去重 ----
        body_data, ctype = multipart_body({"title": title + " 重复"}, "file", "again.md", md_bytes)
        status, body = client.request("POST", "/upload", body_data, ctype)
        check("重复文件提示已存在并给出原链接",
              status == 200 and "已经有人上传过".encode("utf-8") in body and material_id.encode("utf-8") in body,
              "status=%d" % status)
        dup_count = query_one("SELECT COUNT(*) AS c FROM materials WHERE sha256 = ?", (material["sha256"],))["c"]
        check("重复文件没有写入新记录", dup_count == 1, "count=%d" % dup_count)

        # ---- 7. 管理员登录 + 审核通过 ----
        status, body = client.request("GET", "/admin")
        check("未登录访问 /admin 显示登录页", status == 200 and "管理页登录".encode("utf-8") in body, "status=%d" % status)

        form = "token=%s" % TOKEN
        status, body = client.request("POST", "/admin", form.encode(), "application/x-www-form-urlencoded")
        check("用正确令牌登录返回 303 并下发 cookie", status == 303 and client.cookie is not None, "status=%d cookie=%s" % (status, client.cookie))

        form = "action=approve&material_id=%s&reason=selftest+approve" % material_id
        status, body = client.request("POST", "/admin/action", form.encode(), "application/x-www-form-urlencoded")
        check("管理员通过审核返回 303", status == 303, "status=%d" % status)
        material = query_one("SELECT * FROM materials WHERE id = ?", (material_id,))
        check("数据库状态变成 approved", material["status"] == "approved", "status=%s" % material["status"])
        audit = query_one("SELECT * FROM audit_log WHERE material_id = ? AND action = 'approve'", (material_id,))
        check("审核动作写入 audit_log", audit is not None and audit["reason"] == "selftest approve", "")

        # ---- 8. 首页搜索 / 筛选 ----
        status, body = client.request("GET", "/?q=%s" % marker)
        check("搜索能搜到已通过的资料", status == 200 and title.encode("utf-8") in body, "")
        status, body = client.request("GET", "/?course_code=TEST1010")
        check("按课程代码筛选能命中", title.encode("utf-8") in body, "")
        status, body = client.request("GET", "/?course_code=NOPE9999")
        check("筛不到时显示中文空结果", "没有符合条件的资料".encode("utf-8") in body, "")

        # ---- 9. 详情页计数 + 下载计数 ----
        status, body = client.request("GET", "/material/%s" % material_id)
        check("详情页显示标题和完整信息",
              status == 200 and title.encode("utf-8") in body and "TEST1010".encode("utf-8") in body, "")
        check("公开详情页不泄露 original_name", b"my_original_name.md" not in body, "只有管理页能看到原始文件名")
        views_after = query_one("SELECT views FROM materials WHERE id = ?", (material_id,))["views"]
        check("详情页浏览计数增加", views_after >= 1, "views=%d" % views_after)

        status, downloaded = client.request("GET", "/download/%s" % material_id)
        check("下载返回 200 且内容一致", status == 200 and downloaded == md_bytes, "status=%d size=%d" % (status, len(downloaded)))
        downloads_after = query_one("SELECT downloads FROM materials WHERE id = ?", (material_id,))["downloads"]
        check("下载计数 +1", downloads_after == 1, "downloads=%d" % downloads_after)

        # ---- 10. 上传 docx，端到端验证元数据被剥离 ----
        docx_path = os.path.join(work_dir, "meta_%s.docx" % marker)
        make_unique_docx(docx_path, "UNIQUEMARKER" + marker)
        with open(docx_path, "rb") as f:
            docx_bytes = f.read()
        docx_title = "WEBTEST 元数据测试 %s" % marker
        body_data, ctype = multipart_body(
            {"title": docx_title, "course_code": "META1010", "category": "课件"}, "file", "meta.docx", docx_bytes
        )
        status, body = client.request("POST", "/upload", body_data, ctype)
        docx_material = query_one("SELECT * FROM materials WHERE title = ?", (docx_title,))
        check("docx 上传成功", status == 200 and docx_material is not None, "status=%d" % status)
        client.request("POST", "/admin/action",
                       ("action=approve&material_id=%s" % docx_material["id"]).encode(),
                       "application/x-www-form-urlencoded")
        stored_path = os.path.join(BASE_DIR, "data", docx_material["file_key"].replace("/", os.sep))
        check("docx 文件已落盘", os.path.isfile(stored_path), docx_material["file_key"])
        with zipfile.ZipFile(stored_path) as z:
            stored_core = z.read("docProps/core.xml").decode("utf-8")
            stored_app = z.read("docProps/app.xml").decode("utf-8")
        check("落盘的 docx 里作者已被清除",
              "Alice Author" not in stored_core and "Bob Editor" not in stored_core, "core.xml")
        check("落盘的 docx 里公司已被清除", "ACME Corporation" not in stored_app, "app.xml")
        check("落盘的 docx 正文内容仍在", b"UNIQUEMARKER" in zipfile.ZipFile(stored_path).read("word/document.xml"), "正文未被破坏")

        # ---- 11. 举报 3 次自动下架 ----
        for index in range(3):
            form = "material_id=%s&reason=侵权&detail=第%d次" % (material_id, index + 1)
            status, body = client.request("POST", "/report", form.encode(), "application/x-www-form-urlencoded")
        material = query_one("SELECT * FROM materials WHERE id = ?", (material_id,))
        check("举报 3 次后状态自动变成 removed", material["status"] == "removed", "status=%s" % material["status"])
        open_reports = query_one(
            "SELECT COUNT(*) AS c FROM reports WHERE material_id = ? AND status='open'", (material_id,)
        )["c"]
        check("数据库里有 3 条未处理举报", open_reports == 3, "open_reports=%d" % open_reports)
        auto_audit = query_one("SELECT * FROM audit_log WHERE material_id = ? AND action='auto_remove'", (material_id,))
        check("自动下架写入 audit_log", auto_audit is not None, "")
        file_still_there = os.path.isfile(
            os.path.join(BASE_DIR, "data", material["file_key"].replace("/", os.sep))
        )
        check("下架后文件仍在磁盘上（只改状态）", file_still_there, material["file_key"])
        status, body = client.request("GET", "/material/%s" % material_id)
        check("下架资料详情页给出中文提示", "已被下架".encode("utf-8") in body, "")
        status, body = client.request("GET", "/download/%s" % material_id)
        check("下架资料不能下载", status == 404, "status=%d" % status)

        # ---- 12. 管理员看举报列表并恢复 ----
        status, body = client.request("GET", "/admin")
        check("管理页能看到举报列表", status == 200 and "举报列表".encode("utf-8") in body, "")
        status, body = client.request("POST", "/admin/action",
                       ("action=restore&material_id=%s&reason=误报" % material_id).encode(),
                       "application/x-www-form-urlencoded")
        material = query_one("SELECT * FROM materials WHERE id = ?", (material_id,))
        check("管理员恢复后状态回到 approved", material["status"] == "approved", "status=%s" % material["status"])
        status, body = client.request("GET", "/download/%s" % material_id)
        check("恢复后可以重新下载", status == 200, "status=%d" % status)

        # ---- 13. 管理员下架/拒绝动作 ----
        for action, expect in (("reject", "rejected"), ("remove", "removed")):
            client.request("POST", "/admin/action",
                           ("action=%s&material_id=%s" % (action, docx_material["id"])).encode(),
                           "application/x-www-form-urlencoded")
            row = query_one("SELECT status FROM materials WHERE id = ?", (docx_material["id"],))
            check("管理员动作 %s 生效" % action, row["status"] == expect, "status=%s" % row["status"])

    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        output = process.stdout.read().decode("utf-8", "replace") if process.stdout else ""
        print("\n--- 服务端日志（节选） ---")
        print("\n".join(output.splitlines()[-40:]))
        if os.path.isdir(work_dir):
            shutil.rmtree(work_dir, ignore_errors=True)

    failed = [row for row in RESULTS if not row[1]]
    print("\n总计 %d 项，通过 %d 项，失败 %d 项。" % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
