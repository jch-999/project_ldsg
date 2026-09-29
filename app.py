"""
课程资料共享站 · 主程序
======================

只使用 Python 标准库：
    - http.server 提供网页服务
    - sqlite3 存数据
    - 本地文件夹存文件

启动方式：双击 start.bat，或者在本目录执行  python app.py

代码结构：
    app.py       ← 本文件，负责路由和业务逻辑
    db.py        ← 数据库建表和连接
    config.py    ← 读取配置、生成管理令牌
    metadata.py  ← 清除文件元数据（可独立调用）
    pages.py     ← 生成 HTML 页面
"""

import email.parser
import email.policy
import hashlib
import hmac
import json
import mimetypes
import os
import re
import shutil
import sys
import traceback
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlsplit

import config
import db
import metadata
import pages


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

MAX_FILE_SIZE = 50 * 1024 * 1024              # 单文件上限 50 MB
MAX_BODY_SIZE = 52 * 1024 * 1024              # multipart 整个请求的上限，留一点表单余量
PAGE_SIZE = 20                                # 首页每页条数

ALLOWED_EXT = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".zip",
    ".png", ".jpg", ".jpeg", ".md", ".txt", ".epub",
}

ALLOWED_CATEGORIES = {"笔记", "真题", "课件", "教材", "其他"}

REPORT_LIMIT = 3                              # 未处理举报达到这个数量就自动下架


# ---------------------------------------------------------------------------
# 小工具函数
# ---------------------------------------------------------------------------

def now_text():
    """当前时间，格式像 2026-09-29T14:30:00，方便排序和显示。"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def sha256_of_file(path):
    """计算一个文件的 sha256（分块读取，省内存）。"""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def build_canonical_name(course_code, category, semester, material_id, ext):
    """
    生成系统规范文件名，例如 ECEN1010_笔记_2026S1_ab12cd34.pdf。
    原始文件名只保存在数据库的 original_name 字段，管理页才看得到。
    """
    pieces = [p.strip() for p in (course_code or "", category or "", semester or "") if p and p.strip()]
    stem = "_".join(pieces) if pieces else "material"
    # 只保留中英文、数字、下划线和短横线，其余换成下划线
    stem = re.sub(r"[^\w\u4e00-\u9fff\-]+", "_", stem, flags=re.UNICODE).strip("_")
    if not stem:
        stem = "material"
    return "%s_%s%s" % (stem, material_id[:8], ext)


def parse_multipart(content_type, body):
    """
    解析 multipart/form-data 请求体。

    http.server 标准库里没有现成的表单解析器（老旧的 cgi 模块在 Python 3.13
    已被删除），所以这里用标准库的 email 模块来解析，这是官方推荐的替代做法。
    """
    header = b"Content-Type: " + content_type.encode("latin-1") + b"\r\nMIME-Version: 1.0\r\n\r\n"
    message = email.parser.BytesParser(policy=email.policy.default).parsebytes(header + body)
    if not message.is_multipart():
        raise ValueError("请求不是 multipart/form-data 格式")

    fields = {}
    files = []
    for part in message.iter_parts():
        disposition = str(part.get("Content-Disposition") or "")
        if "form-data" not in disposition.lower():
            continue
        name = part.get_param("name", header="content-disposition")
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename is not None:
            files.append({"name": name, "filename": filename, "data": payload})
        elif name:
            charset = part.get_content_charset() or "utf-8"
            fields[name] = payload.decode(charset, "replace").strip()
    return fields, files


# ---------------------------------------------------------------------------
# 服务器上下文：把路径、配置打包在一起
# ---------------------------------------------------------------------------

class Context:
    def __init__(self, base_dir, cfg):
        self.base_dir = base_dir
        self.cfg = cfg
        self.data_dir = os.path.join(base_dir, "data")
        self.upload_dir = os.path.join(self.data_dir, "uploads")
        self.tmp_dir = os.path.join(self.data_dir, "tmp")
        self.db_path = os.path.join(self.data_dir, "materials.db")
        self.admin_token = cfg["admin_token"]
        self.ip_hmac_key = cfg["ip_hmac_key"].encode("utf-8")
        self.cookie_value = hashlib.sha256(self.admin_token.encode("utf-8")).hexdigest()

    def ensure_dirs(self):
        os.makedirs(self.upload_dir, exist_ok=True)
        os.makedirs(self.tmp_dir, exist_ok=True)

    def ip_hmac(self, ip_text):
        """把 IP 地址变成 HMAC 摘要，数据库里不存明文 IP。"""
        return hmac.new(self.ip_hmac_key, (ip_text or "").encode("utf-8"), hashlib.sha256).hexdigest()

    def abs_upload_path(self, file_key):
        """file_key 统一用正斜杠保存，转成本机真实路径。"""
        return os.path.join(self.data_dir, file_key.replace("/", os.sep))


# ---------------------------------------------------------------------------
# HTTP 请求处理器
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "LocalStudyShare/1.0"

    # ---- 通用响应方法 -----------------------------------------------------

    def send_html(self, status, text):
        body = text.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def redirect(self, location):
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

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

    def read_form(self):
        """读取 application/x-www-form-urlencoded 表单。"""
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        body = self.read_body(length)
        parsed = parse_qs(body.decode("utf-8", "replace"), keep_blank_values=True)
        return {key: values[0] for key, values in parsed.items()}

    def get_cookie(self, name):
        raw = self.headers.get("Cookie") or ""
        for piece in raw.split(";"):
            if "=" in piece:
                key, value = piece.split("=", 1)
                if key.strip() == name:
                    return value.strip()
        return None

    def is_admin(self):
        query = parse_qs(urlsplit(self.path).query)
        token = (query.get("token") or [""])[0]
        if token and hmac.compare_digest(token, self.server.context.admin_token):
            return True
        cookie = self.get_cookie("ldsg_admin")
        if cookie:
            return hmac.compare_digest(cookie, self.server.context.cookie_value)
        return False

    def log_message(self, fmt, *args):
        sys.stdout.write("[%s] %s\n" % (datetime.now().strftime("%H:%M:%S"), fmt % args))
        sys.stdout.flush()

    # ---- GET --------------------------------------------------------------

    def do_GET(self):
        try:
            self.route_get()
        except Exception as exc:                      # 兜底，保证不白屏
            self.log_message("处理出错: %r", exc)
            traceback.print_exc()
            self.send_html(500, pages.render_message(
                "服务器出错了",
                "处理这个请求时发生错误：%s" % exc,
                [("/", "回到首页")],
            ))

    def route_get(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query, keep_blank_values=True)

        if path == "/":
            self.page_home(query)
        elif path == "/upload":
            self.send_html(200, pages.render_upload())
        elif path == "/about":
            self.send_html(200, pages.render_about())
        elif path == "/admin":
            self.page_admin(query)
        elif path == "/admin/logout":
            self.clear_admin_cookie()
        elif path.startswith("/material/"):
            self.page_material(path[len("/material/"):])
        elif path.startswith("/download/"):
            self.page_download(path[len("/download/"):])
        elif path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_html(404, pages.render_message(
                "页面不存在", "没有找到 %s 这个地址。" % path, [("/", "回到首页")]
            ))

    # ---- POST -------------------------------------------------------------

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

    def route_post(self):
        parsed = urlsplit(self.path)
        path = parsed.path

        if path == "/upload":
            self.handle_upload()
        elif path == "/report":
            self.handle_report()
        elif path == "/admin":
            self.handle_admin_login()
        elif path == "/admin/action":
            self.handle_admin_action()
        else:
            self.send_html(404, pages.render_message(
                "页面不存在", "没有找到 %s 这个地址。" % path, [("/", "回到首页")]
            ))

    # ---- 首页 / 搜索 / 筛选 ------------------------------------------------

    def page_home(self, query):
        def first(key):
            return (query.get(key) or [""])[0].strip()

        q = first("q")
        course_code = first("course_code")
        category = first("category")
        semester = first("semester")

        try:
            page = int(first("page") or "1")
        except ValueError:
            page = 1
        if page < 1:
            page = 1

        conn = db.get_conn(self.server.context.db_path)
        try:
            where = ["status = 'approved'"]
            params = []
            if q:
                where.append("(title LIKE ? OR course_code LIKE ? OR description LIKE ?)")
                like = "%" + q + "%"
                params += [like, like, like]
            if course_code:
                where.append("course_code = ?")
                params.append(course_code)
            if category:
                where.append("category = ?")
                params.append(category)
            if semester:
                where.append("semester = ?")
                params.append(semester)
            where_sql = " AND ".join(where)

            total_count = conn.execute(
                "SELECT COUNT(*) AS c FROM materials WHERE " + where_sql, params
            ).fetchone()["c"]
            total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
            if page > total_pages:
                page = total_pages

            rows = conn.execute(
                "SELECT * FROM materials WHERE " + where_sql +
                " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                params + [PAGE_SIZE, (page - 1) * PAGE_SIZE],
            ).fetchall()

            def distinct(column):
                data = conn.execute(
                    "SELECT DISTINCT %s AS v FROM materials "
                    "WHERE status='approved' AND %s IS NOT NULL AND %s <> '' ORDER BY v" % (column, column, column)
                ).fetchall()
                return [row["v"] for row in data]

            options = {
                "course_codes": distinct("course_code"),
                "categories": distinct("category"),
                "semesters": distinct("semester"),
            }
        finally:
            conn.close()

        self.send_html(200, pages.render_home(
            rows, total_count, page, total_pages, q, course_code, category, semester, options
        ))

    # ---- 详情 / 下载 ------------------------------------------------------

    def page_material(self, material_id):
        material_id = material_id.strip()
        conn = db.get_conn(self.server.context.db_path)
        try:
            row = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
            if not row:
                self.send_html(404, pages.render_message(
                    "资料不存在", "没有找到这份资料，链接可能已经失效。", [("/", "回到首页")]
                ))
                return
            if row["status"] != "approved":
                status_text = {
                    "pending": "这份资料正在等待管理员审核，通过后才会公开。",
                    "rejected": "这份资料没有通过审核，暂时不可查看。",
                    "removed": "这份资料已被下架，文件仍保存在硬盘上，管理员可以恢复。",
                }.get(row["status"], "这份资料当前不可查看。")
                self.send_html(200, pages.render_message(
                    "资料当前不可查看", status_text,
                    [("/", "回到首页"), ("/upload", "上传资料")],
                ))
                return

            conn.execute(
                "UPDATE materials SET views = views + 1 WHERE id = ?", (material_id,)
            )
            conn.commit()
            row = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
        finally:
            conn.close()

        self.send_html(200, pages.render_material(row))

    def page_download(self, material_id):
        material_id = material_id.strip()
        conn = db.get_conn(self.server.context.db_path)
        try:
            row = conn.execute("SELECT * FROM materials WHERE id = ?", (material_id,)).fetchone()
            if not row or row["status"] != "approved":
                self.send_html(404, pages.render_message(
                    "无法下载", "这份资料不存在，或者还没有通过审核。", [("/", "回到首页")]
                ))
                return
            real_path = self.server.context.abs_upload_path(row["file_key"])
            if not os.path.isfile(real_path):
                self.send_html(404, pages.render_message(
                    "文件不见了", "数据库里有记录，但硬盘上找不到文件。请联系管理员。", [("/", "回到首页")]
                ))
                return

            conn.execute(
                "UPDATE materials SET downloads = downloads + 1, updated_at = ? WHERE id = ?",
                (now_text(), material_id),
            )
            conn.commit()
            file_name = row["file_name"] or (material_id + ".bin")
            content_type = row["mime_type"] or "application/octet-stream"
            file_size = os.path.getsize(real_path)
        finally:
            conn.close()

        ascii_fallback = file_name.encode("ascii", "ignore").decode("ascii") or "material.bin"
        disposition = "attachment; filename=\"%s\"; filename*=UTF-8''%s" % (
            ascii_fallback.replace('"', "_"), quote(file_name)
        )

        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(file_size))
        self.send_header("Content-Disposition", disposition)
        self.end_headers()
        with open(real_path, "rb") as f:
            shutil.copyfileobj(f, self.wfile)

    # ---- 上传 -------------------------------------------------------------

    def handle_upload(self):
        ctx = self.server.context
        content_type = self.headers.get("Content-Type") or ""
        if not content_type.lower().startswith("multipart/form-data"):
            self.send_html(400, pages.render_upload("请求格式不对，请从上传页面重新提交。"))
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_SIZE:
            self.send_html(413, pages.render_upload("整个请求超过 52 MB，请选择更小的文件（单个文件上限 50 MB）。"))
            return

        body = self.read_body(length)
        try:
            fields, files = parse_multipart(content_type, body)
        except Exception as exc:
            self.send_html(400, pages.render_upload("表单解析失败：%s" % exc))
            return

        # 出错时把用户填过的内容回填，避免白填
        form_values = {
            "title": fields.get("title", ""),
            "course_code": fields.get("course_code", ""),
            "course_name": fields.get("course_name", ""),
            "category": fields.get("category", ""),
            "semester": fields.get("semester", ""),
            "tags": fields.get("tags", ""),
            "description": fields.get("description", ""),
            "uploader_note": fields.get("uploader_note", ""),
        }

        if not files:
            self.send_html(400, pages.render_upload("你没有选择文件，请重新选择。", form_values))
            return

        file_part = files[0]
        original_name = os.path.basename((file_part["filename"] or "").replace("\\", "/"))
        data = file_part["data"]
        title = (fields.get("title") or "").strip()

        # ---- 后端校验 1：标题 ----
        if not title:
            self.send_html(400, pages.render_upload("标题不能为空。", form_values))
            return

        # ---- 后端校验 2：扩展名白名单 ----
        ext = os.path.splitext(original_name)[1].lower()
        if ext not in ALLOWED_EXT:
            self.send_html(400, pages.render_upload(
                "不支持的文件类型：%s。允许的类型是 %s。" % (ext or "（无扩展名）", " / ".join(sorted(ALLOWED_EXT))),
                form_values,
            ))
            return

        # ---- 后端校验 3：文件大小（这是绕过前端也必须过的关） ----
        if len(data) == 0:
            self.send_html(400, pages.render_upload("文件是空的，请重新选择。", form_values))
            return
        if len(data) > MAX_FILE_SIZE:
            self.send_html(413, pages.render_upload(
                "文件太大：%.1f MB，上限 50 MB。" % (len(data) / 1024 / 1024), form_values
            ))
            return

        category = (fields.get("category") or "").strip()
        if category and category not in ALLOWED_CATEGORIES:
            category = "其他"

        tags_raw = (fields.get("tags") or "").strip()
        tag_list = [t.strip() for t in re.split(r"[,，;；、]+", tags_raw) if t.strip()]
        tags_json = json.dumps(tag_list, ensure_ascii=False) if tag_list else None

        material_id = uuid.uuid4().hex
        created_at = now_text()

        # ---- 清除元数据（调用独立函数，和上传逻辑解耦） ----
        tmp_in = os.path.join(ctx.tmp_dir, material_id + "_in" + ext)
        tmp_out = os.path.join(ctx.tmp_dir, material_id + "_out" + ext)
        with open(tmp_in, "wb") as f:
            f.write(data)
        try:
            result = metadata.strip_metadata(tmp_in, tmp_out)
        except Exception as exc:
            self.remove_quietly(tmp_in)
            self.remove_quietly(tmp_out)
            self.send_html(500, pages.render_upload(
                "清除文件元数据时出错，为避免泄露隐私，本次上传没有保存。原因：%s" % exc, form_values
            ))
            return
        finally:
            self.remove_quietly(tmp_in)

        sha256_value = sha256_of_file(tmp_out)
        file_size = os.path.getsize(tmp_out)

        # ---- sha256 去重 ----
        conn = db.get_conn(ctx.db_path)
        try:
            existed = conn.execute(
                "SELECT id, title, status FROM materials WHERE sha256 = ? ORDER BY created_at DESC LIMIT 1",
                (sha256_value,),
            ).fetchone()
            if existed:
                self.remove_quietly(tmp_out)
                self.send_html(200, pages.render_upload(duplicate=existed, values=form_values))
                return

            file_key = "uploads/%s_%s%s" % (sha256_value[:16], material_id[:8], ext)
            file_name = build_canonical_name(
                fields.get("course_code", ""), category, fields.get("semester", ""), material_id, ext
            )
            mime_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
            real_path = ctx.abs_upload_path(file_key)
            shutil.move(tmp_out, real_path)

            ip_hmac = ctx.ip_hmac(self.client_address[0])
            conn.execute(
                "INSERT INTO materials ("
                "id, title, description, course_code, course_name, category, semester, tags,"
                "file_key, file_name, original_name, file_size, mime_type, sha256,"
                "uploader_note, upload_credential, status, downloads, views, ip_hmac, created_at, updated_at"
                ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    material_id, title, fields.get("description", ""), fields.get("course_code", ""),
                    fields.get("course_name", ""), category, fields.get("semester", ""), tags_json,
                    file_key, file_name, original_name, file_size, mime_type, sha256_value,
                    fields.get("uploader_note", ""), None, "pending", 0, 0, ip_hmac,
                    created_at, created_at,
                ),
            )
            conn.execute(
                "INSERT INTO material_sources (material_id, provider, object_key, size, sha256, priority) "
                "VALUES (?,?,?,?,?,?)",
                (material_id, "local", file_key, file_size, sha256_value, 0),
            )
            conn.execute(
                "INSERT INTO audit_log (id, material_id, action, reason, actor, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (uuid.uuid4().hex, material_id, "upload", "用户上传，等待审核", "uploader", created_at),
            )
            conn.commit()
        finally:
            conn.close()

        self.send_html(200, pages.render_message(
            "上传成功，等待审核",
            "《%s》已保存。管理员审核通过后，它才会出现在首页。"
            "系统已执行元数据清除：%s" % (title, result["note"]),
            [("/", "回到首页"), ("/upload", "再传一份")],
        ))

    def remove_quietly(self, path):
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass

    # ---- 举报 -------------------------------------------------------------

    def handle_report(self):
        form = self.read_form()
        material_id = (form.get("material_id") or "").strip()
        reason = (form.get("reason") or "其他").strip()
        detail = (form.get("detail") or "").strip()
        if not material_id:
            self.send_html(400, pages.render_message("举报失败", "缺少资料编号。", [("/", "回到首页")]))
            return

        ctx = self.server.context
        conn = db.get_conn(ctx.db_path)
        try:
            row = conn.execute("SELECT id, title, status FROM materials WHERE id = ?", (material_id,)).fetchone()
            if not row:
                self.send_html(404, pages.render_message("举报失败", "这份资料不存在。", [("/", "回到首页")]))
                return

            created_at = now_text()
            conn.execute(
                "INSERT INTO reports (id, material_id, reason, detail, ip_hmac, status, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (uuid.uuid4().hex, material_id, reason, detail, ctx.ip_hmac(self.client_address[0]), "open", created_at),
            )

            open_count = conn.execute(
                "SELECT COUNT(*) AS c FROM reports WHERE material_id = ? AND status = 'open'", (material_id,)
            ).fetchone()["c"]

            auto_removed = False
            if open_count >= REPORT_LIMIT and row["status"] != "removed":
                conn.execute(
                    "UPDATE materials SET status='removed', review_note=?, reviewed_at=?, reviewer=?, updated_at=? "
                    "WHERE id=?",
                    ("未处理举报累计达到 %d 次，系统自动下架" % REPORT_LIMIT, created_at, "system", created_at, material_id),
                )
                conn.execute(
                    "INSERT INTO audit_log (id, material_id, action, reason, actor, created_at) VALUES (?,?,?,?,?,?)",
                    (uuid.uuid4().hex, material_id, "auto_remove",
                     "未处理举报累计达到 %d 次" % REPORT_LIMIT, "system", created_at),
                )
                auto_removed = True
            conn.commit()
        finally:
            conn.close()

        extra = ""
        if auto_removed:
            extra = "该资料的未处理举报已达到 %d 次，系统已自动将其下架。" % REPORT_LIMIT
        self.send_html(200, pages.render_message(
            "举报已提交",
            "谢谢，你的举报已经记录。管理员会尽快处理。" + extra,
            [("/", "回到首页"), ("/material/%s" % material_id, "返回资料页")],
        ))

    # ---- 管理页 -----------------------------------------------------------

    def handle_admin_login(self):
        form = self.read_form()
        token = (form.get("token") or "").strip()
        if token and hmac.compare_digest(token, self.server.context.admin_token):
            self.send_response(303)
            self.send_header("Location", "/admin")
            self.send_header(
                "Set-Cookie",
                "ldsg_admin=%s; Path=/; HttpOnly; SameSite=Lax" % self.server.context.cookie_value,
            )
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self.send_html(401, pages.render_admin_login("令牌不对，请重新输入。"))

    def clear_admin_cookie(self):
        self.send_response(303)
        self.send_header("Location", "/admin")
        self.send_header("Set-Cookie", "ldsg_admin=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def page_admin(self, query):
        if not self.is_admin():
            token = (query.get("token") or [""])[0]
            error = "令牌不对，请重新输入。" if token else None
            self.send_html(200 if not error else 401, pages.render_admin_login(error))
            return

        conn = db.get_conn(self.server.context.db_path)
        try:
            counts = {"pending": 0, "approved": 0, "rejected": 0, "removed": 0, "open_reports": 0}
            for row in conn.execute("SELECT status, COUNT(*) AS c FROM materials GROUP BY status"):
                if row["status"] in counts:
                    counts[row["status"]] = row["c"]
            counts["open_reports"] = conn.execute(
                "SELECT COUNT(*) AS c FROM reports WHERE status = 'open'"
            ).fetchone()["c"]

            materials = conn.execute(
                "SELECT m.*, (SELECT COUNT(*) FROM reports r WHERE r.material_id = m.id AND r.status='open') "
                "AS report_count FROM materials m "
                "ORDER BY CASE m.status WHEN 'pending' THEN 0 ELSE 1 END, m.created_at DESC"
            ).fetchall()

            reports = conn.execute(
                "SELECT r.*, m.title AS material_title FROM reports r "
                "LEFT JOIN materials m ON m.id = r.material_id "
                "ORDER BY CASE r.status WHEN 'open' THEN 0 ELSE 1 END, r.created_at DESC"
            ).fetchall()
        finally:
            conn.close()

        self.send_html(200, pages.render_admin(materials, reports, counts))

    def handle_admin_action(self):
        if not self.is_admin():
            self.send_html(401, pages.render_admin_login("登录状态已失效，请重新输入令牌。"))
            return

        form = self.read_form()
        action = (form.get("action") or "").strip()
        material_id = (form.get("material_id") or "").strip()
        reason = (form.get("reason") or "").strip()
        actor = "admin"
        created_at = now_text()

        status_map = {
            "approve": "approved",
            "reject": "rejected",
            "remove": "removed",
            "restore": "approved",
        }

        conn = db.get_conn(self.server.context.db_path)
        try:
            if action == "handle_report":
                report_id = (form.get("report_id") or "").strip()
                report = conn.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
                if not report:
                    self.send_html(404, pages.render_message("操作失败", "找不到这条举报。", [("/admin", "回管理页")]))
                    return
                conn.execute("UPDATE reports SET status = 'handled' WHERE id = ?", (report_id,))
                conn.execute(
                    "INSERT INTO audit_log (id, material_id, action, reason, actor, created_at) VALUES (?,?,?,?,?,?)",
                    (uuid.uuid4().hex, report["material_id"], "handle_report", reason or "标记举报已处理", actor, created_at),
                )
            elif action in status_map:
                if not material_id:
                    self.send_html(400, pages.render_message("操作失败", "缺少资料编号。", [("/admin", "回管理页")]))
                    return
                row = conn.execute("SELECT id FROM materials WHERE id = ?", (material_id,)).fetchone()
                if not row:
                    self.send_html(404, pages.render_message("操作失败", "找不到这份资料。", [("/admin", "回管理页")]))
                    return
                conn.execute(
                    "UPDATE materials SET status=?, review_note=?, reviewed_at=?, reviewer=?, updated_at=? WHERE id=?",
                    (status_map[action], reason, created_at, actor, created_at, material_id),
                )
                conn.execute(
                    "INSERT INTO audit_log (id, material_id, action, reason, actor, created_at) VALUES (?,?,?,?,?,?)",
                    (uuid.uuid4().hex, material_id, action, reason, actor, created_at),
                )
            else:
                self.send_html(400, pages.render_message("操作失败", "不认识的操作：%s。" % action, [("/admin", "回管理页")]))
                return
            conn.commit()
        finally:
            conn.close()

        self.redirect("/admin")


# ---------------------------------------------------------------------------
# 启动
# ---------------------------------------------------------------------------

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cfg = config.load_config(base_dir)
    ctx = Context(base_dir, cfg)
    ctx.ensure_dirs()
    db.init_db(ctx.db_path)

    server = None
    port = cfg["port"]
    for candidate in range(port, port + 10):
        try:
            server = ThreadingHTTPServer((cfg["host"], candidate), Handler)
            port = candidate
            break
        except OSError:
            continue

    if server is None:
        print("无法启动：%s 的 %d~%d 端口都被占用了。" % (cfg["host"], cfg["port"], cfg["port"] + 9))
        return 1

    server.context = ctx
    url = "http://%s:%d" % (cfg["host"], port)

    print("=" * 62)
    print(" 课程资料共享站 已启动")
    print(" 请在浏览器打开下面的地址：")
    print("")
    print("   首页：   %s/" % url)
    print("   上传：   %s/upload" % url)
    print("   管理页： %s/admin" % url)
    print("   关于：   %s/about" % url)
    print("")
    print(" 管理令牌：%s" % cfg["admin_token"])
    print(" （令牌也可以改 config.ini 里的 admin_token，或用环境变量 LDSG_ADMIN_TOKEN 覆盖）")
    print("")
    print(" 停止服务：在本窗口按 Ctrl+C")
    print("=" * 62)
    print("", flush=True)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止服务。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
