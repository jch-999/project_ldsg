"""
页面模板模块
============

本项目不引入任何前端框架，所有 HTML 都是用 Python 字符串拼出来的。
这个文件集中存放「长什么样」的代码，app.py 只管「做什么」。

面向初学者的说明：
    - layout() 是每一页的外壳（导航栏 + 样式）
    - 其他 render_xxx() 函数各自返回一页的正文
    - html.escape() 用来把用户输入转义，防止把 HTML 注入页面
"""

import html
import json
from urllib.parse import urlencode


def esc(value):
    """转义 HTML 特殊字符。None 当成空字符串处理。"""
    if value is None:
        return ""
    return html.escape(str(value))


def qs(**params):
    """把关键字参数拼成查询字符串，值为 None 或空串的会丢掉。"""
    cleaned = {k: v for k, v in params.items() if v not in (None, "")}
    return urlencode(cleaned)


BASE_CSS = """
:root {
  --bg: #f4f6f9;
  --card: #ffffff;
  --ink: #1f2933;
  --muted: #6b7280;
  --line: #e3e8ef;
  --brand: #2f6feb;
  --brand-dark: #1d4ed8;
  --ok: #0f9d58;
  --warn: #d97706;
  --bad: #dc2626;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--ink);
  font-family: "Microsoft YaHei", "PingFang SC", system-ui, sans-serif;
  font-size: 15px;
  line-height: 1.6;
}
a { color: var(--brand); text-decoration: none; }
a:hover { text-decoration: underline; }
header.topbar {
  background: #fff;
  border-bottom: 1px solid var(--line);
  padding: 12px 0;
}
.wrap { max-width: 1000px; margin: 0 auto; padding: 0 16px; }
.topbar .wrap { display: flex; align-items: center; gap: 18px; flex-wrap: wrap; }
.brand { font-size: 18px; font-weight: 700; color: var(--ink); }
.brand span { color: var(--brand); }
nav a { margin-right: 14px; color: var(--muted); }
nav a.active { color: var(--brand); font-weight: 600; }
main { padding: 22px 0 60px; }
h1 { font-size: 22px; margin: 6px 0 16px; }
h2 { font-size: 17px; margin: 22px 0 10px; }
.card {
  background: var(--card);
  border: 1px solid var(--line);
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 14px;
}
.muted { color: var(--muted); }
.small { font-size: 13px; }
.row { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; }
.grow { flex: 1 1 220px; }
input[type=text], input[type=search], input[type=password], select, textarea {
  width: 100%;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: 8px;
  font: inherit;
  background: #fff;
  color: var(--ink);
}
textarea { min-height: 80px; resize: vertical; }
label.field { display: block; margin-bottom: 10px; }
label.field .label-text { display: block; font-size: 13px; color: var(--muted); margin-bottom: 4px; }
button, .btn {
  display: inline-block;
  border: 0;
  background: var(--brand);
  color: #fff;
  padding: 8px 16px;
  border-radius: 8px;
  font: inherit;
  cursor: pointer;
}
button:hover, .btn:hover { background: var(--brand-dark); text-decoration: none; }
button.ghost, .btn.ghost { background: #fff; color: var(--brand); border: 1px solid var(--brand); }
button.danger { background: var(--bad); }
button.ghost-danger { background: #fff; color: var(--bad); border: 1px solid var(--bad); }
button.small-btn { padding: 5px 10px; font-size: 13px; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 9px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { font-size: 13px; color: var(--muted); font-weight: 600; }
.tag {
  display: inline-block; background: #eef3ff; color: var(--brand);
  border-radius: 999px; padding: 1px 9px; font-size: 12px; margin: 0 4px 4px 0;
}
.badge { border-radius: 999px; padding: 1px 9px; font-size: 12px; display: inline-block; }
.badge.pending { background: #fff7e6; color: var(--warn); }
.badge.approved { background: #e8f6ee; color: var(--ok); }
.badge.rejected { background: #fdeaea; color: var(--bad); }
.badge.removed { background: #f1f2f4; color: var(--muted); }
.flash { border-radius: 8px; padding: 10px 12px; margin-bottom: 14px; }
.flash.info { background: #eef3ff; color: #1d4ed8; }
.flash.ok { background: #e8f6ee; color: #0b6b3a; }
.flash.bad { background: #fdeaea; color: #9b1c1c; }
.pager { display: flex; gap: 8px; align-items: center; margin-top: 8px; flex-wrap: wrap; }
.pager a, .pager span.current {
  border: 1px solid var(--line); background: #fff; border-radius: 6px;
  padding: 4px 10px; color: var(--ink);
}
.pager span.current { background: var(--brand); color: #fff; border-color: var(--brand); }
.dropzone {
  border: 2px dashed #b9c4d4; border-radius: 10px; padding: 26px;
  text-align: center; color: var(--muted); background: #fbfcfe; cursor: pointer;
}
.dropzone.hover { border-color: var(--brand); background: #eef3ff; color: var(--brand); }
.empty { text-align: center; color: var(--muted); padding: 34px 10px; }
.meta-grid { display: grid; grid-template-columns: 130px 1fr; gap: 6px 12px; }
.meta-grid .k { color: var(--muted); font-size: 13px; }
footer { color: var(--muted); font-size: 13px; padding: 20px 0 40px; text-align: center; }
details { margin-top: 8px; }
summary { cursor: pointer; color: var(--brand); }
"""


# 表单提交时给用户一个「加载中」的反馈。
# 只对没有 name 属性的按钮生效，避免管理员那几个带 name=action 的按钮
# 在提交瞬间被禁用后丢掉自己的值。
SUBMIT_FEEDBACK_JS = """
(function () {
  document.addEventListener("submit", function (e) {
    if (e.defaultPrevented) { return; }
    var button = e.submitter;
    if (!button || button.hasAttribute("name")) { return; }
    button.disabled = true;
    button.textContent = button.getAttribute("data-loading") || "提交中…";
  });
})();
"""


def layout(title, body, active=""):
    """给正文套上统一的页面外壳。"""

    def nav_item(href, text, key):
        klass = ' class="active"' if active == key else ""
        return '<a href="%s"%s>%s</a>' % (href, klass, text)

    return (
        "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        "<title>%s · 课程资料共享</title>\n"
        "<style>%s</style>\n"
        "</head>\n<body>\n"
        "<header class=\"topbar\"><div class=\"wrap\">"
        "<div class=\"brand\">课程资料<span>共享站</span></div>"
        "<nav>%s %s %s %s</nav>"
        "</div></header>\n"
        "<main class=\"wrap\">%s</main>\n"
        "<footer>本机运行的课程资料共享站 · 本期为本地版本，无云端依赖</footer>\n"
        "<script>%s</script>\n"
        "</body></html>"
        % (
            esc(title),
            BASE_CSS,
            nav_item("/", "首页", "home"),
            nav_item("/upload", "上传资料", "upload"),
            nav_item("/admin", "管理页", "admin"),
            nav_item("/about", "关于", "about"),
            body,
            SUBMIT_FEEDBACK_JS,
        )
    )


def flash(kind, text):
    """一条提示条。kind 取 info / ok / bad。"""
    return '<div class="flash %s">%s</div>' % (esc(kind), esc(text))


def _tags_html(tags_text):
    if not tags_text:
        return ""
    try:
        tags = json.loads(tags_text)
    except (ValueError, TypeError):
        return ""
    if not isinstance(tags, list):
        return ""
    return "".join('<span class="tag">%s</span>' % esc(t) for t in tags)


def _status_badge(status):
    labels = {
        "pending": "待审核",
        "approved": "已通过",
        "rejected": "已拒绝",
        "removed": "已下架",
    }
    label = labels.get(status, status or "未知")
    return '<span class="badge %s">%s</span>' % (esc(status or "unknown"), esc(label))


def render_home(rows, total_count, page, total_pages, q, course_code, category, semester, options):
    """首页：搜索 + 筛选 + 列表 + 分页。"""
    parts = []

    parts.append("<h1>资料库</h1>")

    # --- 搜索和筛选表单 ---
    form = ['<form class="card" method="get" action="/">']
    form.append('<div class="row">')
    form.append('<input class="grow" type="search" name="q" placeholder="搜索标题 / 课程代码 / 简介，回车或点按钮" value="%s">' % esc(q))
    form.append('<button type="submit">搜索</button>')
    form.append('</div>')
    form.append('<div class="row" style="margin-top:10px">')
    form.append('<div class="grow"><label class="field"><span class="label-text">课程代码</span>'
                '<select name="course_code">%s</select></label></div>' % _select_options(options["course_codes"], course_code, "全部课程"))
    form.append('<div class="grow"><label class="field"><span class="label-text">类别</span>'
                '<select name="category">%s</select></label></div>' % _select_options(options["categories"], category, "全部类别"))
    form.append('<div class="grow"><label class="field"><span class="label-text">学期</span>'
                '<select name="semester">%s</select></label></div>' % _select_options(options["semesters"], semester, "全部学期"))
    form.append('</div>')
    form.append('<div class="row"><button type="submit">应用筛选</button>'
                '<a class="btn ghost" href="/">清空条件</a></div>')
    form.append('</form>')
    parts.append("".join(form))

    # --- 结果计数 ---
    if rows:
        parts.append('<p class="muted small">共找到 %d 条资料，第 %d / %d 页。</p>' % (total_count, page, total_pages))
    else:
        parts.append('<p class="muted small">共找到 %d 条资料。</p>' % total_count)

    # --- 列表 ---
    if not rows:
        if q or course_code or category or semester:
            text = "没有符合条件的资料。试试换一个关键词，或者点“清空条件”。"
        else:
            text = "资料库现在还是空的。你可以点上方“上传资料”来添加第一份。"
        parts.append('<div class="card empty">%s</div>' % esc(text))
    else:
        for row in rows:
            tags_html = _tags_html(row["tags"])
            description = row["description"] or "（没有填写简介）"
            if len(description) > 130:
                description = description[:130] + "…"
            parts.append(
                '<div class="card">'
                '<h2 style="margin-top:0"><a href="/material/%s">%s</a></h2>'
                '<div class="muted small">%s · %s · %s · 上传于 %s</div>'
                '<p>%s</p>'
                '<div>%s</div>'
                '<div class="muted small">下载 %d 次 · 浏览 %d 次</div>'
                '</div>'
                % (
                    esc(row["id"]),
                    esc(row["title"]),
                    esc(row["course_code"] or "未填课程代码"),
                    esc(row["category"] or "未分类"),
                    esc(row["semester"] or "未填学期"),
                    esc((row["created_at"] or "")[:10]),
                    esc(description),
                    tags_html,
                    row["downloads"] or 0,
                    row["views"] or 0,
                )
            )

    # --- 分页 ---
    if total_pages > 1:
        pager = ['<div class="pager">']
        base = dict(q=q, course_code=course_code, category=category, semester=semester)
        if page > 1:
            pager.append('<a href="/?%s">上一页</a>' % qs(page=page - 1, **base))
        else:
            pager.append('<span class="muted small">上一页</span>')
        pager.append('<span class="current">%d</span>' % page)
        pager.append('<span class="muted small">共 %d 页</span>' % total_pages)
        if page < total_pages:
            pager.append('<a href="/?%s">下一页</a>' % qs(page=page + 1, **base))
        else:
            pager.append('<span class="muted small">下一页</span>')
        pager.append('</div>')
        parts.append("".join(pager))

    return layout("资料库", "".join(parts), "home")


def _select_options(values, selected, all_label):
    out = ['<option value="">%s</option>' % esc(all_label)]
    for value in values:
        mark = " selected" if value == selected else ""
        out.append('<option value="%s"%s>%s</option>' % (esc(value), mark, esc(value)))
    return "".join(out)


UPLOAD_FORM_JS = """
(function () {
  var zone = document.getElementById("dropzone");
  var input = document.getElementById("file-input");
  var nameBox = document.getElementById("file-name");
  var errorBox = document.getElementById("client-error");
  var allowed = ["pdf","docx","pptx","xlsx","zip","png","jpg","jpeg","md","txt","epub"];
  var maxBytes = 50 * 1024 * 1024;

  function showError(msg) {
    errorBox.textContent = msg || "";
    errorBox.style.display = msg ? "block" : "none";
  }

  function check(file) {
    if (!file) { return false; }
    var dot = file.name.lastIndexOf(".");
    var ext = dot >= 0 ? file.name.slice(dot + 1).toLowerCase() : "";
    if (allowed.indexOf(ext) < 0) {
      showError("不支持的文件类型：" + (ext || "无扩展名") + "。允许：" + allowed.join(" / "));
      return false;
    }
    if (file.size > maxBytes) {
      showError("文件太大：" + (file.size / 1024 / 1024).toFixed(1) + " MB，上限 50 MB。");
      return false;
    }
    showError("");
    return true;
  }

  function bind(file) {
    if (!check(file)) { input.value = ""; nameBox.textContent = ""; return; }
    nameBox.textContent = "已选择：" + file.name + "（" + (file.size / 1024 / 1024).toFixed(2) + " MB）";
  }

  if (zone) {
    zone.addEventListener("click", function () { input.click(); });
    ["dragenter", "dragover"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) { e.preventDefault(); zone.classList.add("hover"); });
    });
    ["dragleave", "drop"].forEach(function (evt) {
      zone.addEventListener(evt, function (e) { e.preventDefault(); zone.classList.remove("hover"); });
    });
    zone.addEventListener("drop", function (e) {
      if (e.dataTransfer.files.length > 0) {
        input.files = e.dataTransfer.files;
        bind(e.dataTransfer.files[0]);
      }
    });
  }
  if (input) {
    input.addEventListener("change", function () { bind(input.files[0]); });
  }
  var form = document.getElementById("upload-form");
  if (form) {
    form.addEventListener("submit", function (e) {
      var file = input && input.files[0];
      if (!file) { e.preventDefault(); showError("请先选择一个文件。"); return; }
      if (!check(file)) { e.preventDefault(); }
    });
  }
})();
"""


def render_upload(error=None, values=None, duplicate=None):
    """上传页。values 用来在出错时回填用户已经填过的内容。"""
    values = values or {}
    parts = ["<h1>上传资料</h1>"]

    if error:
        parts.append(flash("bad", error))
    if duplicate:
        parts.append(
            '<div class="flash info">这个文件已经有人上传过，没有重复保存。'
            '原资料链接：<a href="/material/%s">%s</a></div>'
            % (esc(duplicate["id"]), esc(duplicate["title"]))
        )

    parts.append(
        '<div class="flash info">上传后资料进入“待审核”状态，不会马上公开。'
        '单个文件不超过 50 MB。系统会自动清除文档和图片里的作者 / 公司 / EXIF 等元数据。</div>'
    )

    # 类别下拉
    categories = ["笔记", "真题", "课件", "教材", "其他"]
    category_selected = values.get("category", "")
    category_options = ['<option value="">请选择</option>']
    for item in categories:
        mark = " selected" if item == category_selected else ""
        category_options.append('<option value="%s"%s>%s</option>' % (esc(item), mark, esc(item)))

    parts.append('<form id="upload-form" class="card" method="post" action="/upload" enctype="multipart/form-data">')
    parts.append('<div id="client-error" class="flash bad" style="display:none"></div>')
    parts.append('<div id="dropzone" class="dropzone">把文件拖到这里，或者点这里选择文件<br>'
                 '<span class="small">pdf / docx / pptx / xlsx / zip / png / jpg / md / txt / epub，≤ 50 MB</span></div>')
    parts.append('<input id="file-input" type="file" name="file" style="display:none" '
                 'accept=".pdf,.docx,.pptx,.xlsx,.zip,.png,.jpg,.jpeg,.md,.txt,.epub">')
    parts.append('<div id="file-name" class="small muted" style="margin:8px 0 14px"></div>')

    parts.append('<label class="field"><span class="label-text">标题（必填）</span>'
                 '<input type="text" name="title" required value="%s"></label>' % esc(values.get("title", "")))
    parts.append('<div class="row">')
    parts.append('<div class="grow"><label class="field"><span class="label-text">课程代码</span>'
                 '<input type="text" name="course_code" placeholder="例如 ECEN1010" value="%s"></label></div>'
                 % esc(values.get("course_code", "")))
    parts.append('<div class="grow"><label class="field"><span class="label-text">课程名称</span>'
                 '<input type="text" name="course_name" value="%s"></label></div>' % esc(values.get("course_name", "")))
    parts.append('</div>')
    parts.append('<div class="row">')
    parts.append('<div class="grow"><label class="field"><span class="label-text">类别</span>'
                 '<select name="category">%s</select></label></div>' % "".join(category_options))
    parts.append('<div class="grow"><label class="field"><span class="label-text">学期</span>'
                 '<input type="text" name="semester" placeholder="例如 2026S1" value="%s"></label></div>'
                 % esc(values.get("semester", "")))
    parts.append('</div>')
    parts.append('<label class="field"><span class="label-text">标签（用逗号分隔）</span>'
                 '<input type="text" name="tags" placeholder="例如 期末,重点,公式" value="%s"></label>'
                 % esc(values.get("tags", "")))
    parts.append('<label class="field"><span class="label-text">简介</span>'
                 '<textarea name="description">%s</textarea></label>' % esc(values.get("description", "")))
    parts.append('<label class="field"><span class="label-text">上传者昵称（可空，别人能看到）</span>'
                 '<input type="text" name="uploader_note" value="%s"></label>' % esc(values.get("uploader_note", "")))
    parts.append('<button type="submit">提交上传</button>')
    parts.append('</form>')
    parts.append("<script>%s</script>" % UPLOAD_FORM_JS)
    return layout("上传资料", "".join(parts), "upload")


def render_material(material, tags_text=""):
    """详情页。material 是一行 sqlite3.Row。"""
    parts = ['<h1>%s</h1>' % esc(material["title"])]
    parts.append('<div class="card">')
    parts.append('<p>%s</p>' % esc(material["description"] or "（没有填写简介）"))
    parts.append('<div>%s</div>' % _tags_html(material["tags"]))
    parts.append('<div class="meta-grid">')
    rows = [
        ("课程代码", material["course_code"]),
        ("课程名称", material["course_name"]),
        ("类别", material["category"]),
        ("学期", material["semester"]),
        ("规范文件名", material["file_name"]),
        ("文件大小", _human_size(material["file_size"])),
        ("文件类型", material["mime_type"]),
        ("上传者昵称", material["uploader_note"]),
        ("上传时间", material["created_at"]),
        ("下载次数", str(material["downloads"] or 0)),
        ("浏览次数", str(material["views"] or 0)),
    ]
    for key, value in rows:
        parts.append('<div class="k">%s</div><div>%s</div>' % (esc(key), esc(value if value not in (None, "") else "—")))
    parts.append('</div>')
    parts.append('<div class="row" style="margin-top:16px">'
                 '<a class="btn" href="/download/%s">下载文件</a></div>' % esc(material["id"]))
    parts.append('</div>')

    # 举报表单
    parts.append('<div class="card">')
    parts.append('<h2 style="margin-top:0">举报这份资料</h2>')
    parts.append(
        '<form method="post" action="/report">'
        '<input type="hidden" name="material_id" value="%s">'
        '<label class="field"><span class="label-text">原因</span>'
        '<select name="reason">'
        '<option value="侵权">侵权</option>'
        '<option value="内容错误">内容错误</option>'
        '<option value="无法下载">无法下载</option>'
        '<option value="其他">其他</option>'
        '</select></label>'
        '<label class="field"><span class="label-text">补充说明（可空）</span>'
        '<textarea name="detail"></textarea></label>'
        '<button class="ghost-danger" type="submit">提交举报</button>'
        '</form>'
        '<p class="small muted">同一份资料累计 3 条未处理举报会自动下架，文件不会删除。</p>'
        % esc(material["id"])
    )
    parts.append('</div>')
    return layout(material["title"], "".join(parts), "home")


def _human_size(size):
    if size is None:
        return "—"
    size = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.1f %s" % (size, unit) if unit != "B" else "%d B" % int(size)
        size /= 1024
    return "—"


def render_message(title, text, links=None):
    """通用提示页：空结果 / 出错都用它，保证不白屏。"""
    parts = ['<h1>%s</h1>' % esc(title)]
    parts.append('<div class="card"><p>%s</p>' % esc(text))
    if links:
        parts.append('<div class="row">')
        for href, label in links:
            parts.append('<a class="btn ghost" href="%s">%s</a>' % (esc(href), esc(label)))
        parts.append('</div>')
    parts.append('</div>')
    return layout(title, "".join(parts))


def render_admin_login(error=None):
    parts = ['<h1>管理页登录</h1>']
    if error:
        parts.append(flash("bad", error))
    parts.append(
        '<div class="card">'
        '<p class="muted">管理令牌在启动时的控制台里会打印，也存在 config.ini 的 admin_token 项。'
        '也可以用环境变量 LDSG_ADMIN_TOKEN 覆盖。</p>'
        '<form method="post" action="/admin">'
        '<label class="field"><span class="label-text">管理令牌</span>'
        '<input type="password" name="token" autocomplete="current-password"></label>'
        '<button type="submit">进入管理页</button>'
        '</form></div>'
    )
    return layout("管理页登录", "".join(parts), "admin")


def render_admin(materials, reports, counts):
    """管理页：待审 / 举报 / 全部。"""
    parts = ['<h1>管理页</h1>']
    parts.append(
        '<div class="row">'
        '<span class="badge pending">待审核 %d</span>'
        '<span class="badge approved">已通过 %d</span>'
        '<span class="badge rejected">已拒绝 %d</span>'
        '<span class="badge removed">已下架 %d</span>'
        '<span class="badge">未处理举报 %d</span>'
        '<a class="btn ghost small-btn" href="/admin/logout">退出登录</a>'
        '</div>'
        % (
            counts.get("pending", 0),
            counts.get("approved", 0),
            counts.get("rejected", 0),
            counts.get("removed", 0),
            counts.get("open_reports", 0),
        )
    )

    # --- 举报列表 ---
    parts.append("<h2>举报列表</h2>")
    if not reports:
        parts.append('<div class="card empty">目前没有举报。</div>')
    else:
        parts.append('<div class="card"><table><tr><th>时间</th><th>资料</th><th>原因</th><th>说明</th><th>状态</th><th>操作</th></tr>')
        for report in reports:
            parts.append(
                '<tr><td class="small">%s</td><td><a href="/material/%s">%s</a></td>'
                '<td>%s</td><td class="small">%s</td><td>%s</td>'
                '<td>%s</td></tr>'
                % (
                    esc((report["created_at"] or "")[:16]),
                    esc(report["material_id"]),
                    esc(report["material_title"] or report["material_id"]),
                    esc(report["reason"]),
                    esc(report["detail"]),
                    esc(report["status"]),
                    _report_action_form(report["id"]) if report["status"] == "open" else "",
                )
            )
        parts.append('</table></div>')

    # --- 资料列表 ---
    parts.append("<h2>资料列表</h2>")
    if not materials:
        parts.append('<div class="card empty">还没有任何资料。</div>')
    else:
        for m in materials:
            parts.append(_admin_material_card(m))

    return layout("管理页", "".join(parts), "admin")


def _report_action_form(report_id):
    return (
        '<form method="post" action="/admin/action">'
        '<input type="hidden" name="action" value="handle_report">'
        '<input type="hidden" name="report_id" value="%s">'
        '<button class="ghost small-btn" type="submit">标记已处理</button>'
        '</form>' % esc(report_id)
    )


def _admin_material_card(m):
    parts = ['<div class="card">']
    parts.append('<div class="row"><strong class="grow">%s</strong>%s</div>' % (esc(m["title"]), _status_badge(m["status"])))
    parts.append(
        '<div class="small muted">ID %s · %s · %s · %s · 上传时间 %s</div>'
        % (esc(m["id"]), esc(m["course_code"] or "无课程代码"), esc(m["category"] or "未分类"),
           esc(m["semester"] or "无学期"), esc((m["created_at"] or "")[:16]))
    )
    parts.append('<div class="small muted">原始文件名（仅管理员可见）：%s</div>' % esc(m["original_name"]))
    parts.append('<div class="small muted">规范文件名：%s · %s · 举报数 %d</div>'
                 % (esc(m["file_name"]), _human_size(m["file_size"]), m["report_count"] or 0))
    if m["review_note"]:
        parts.append('<div class="small">审核备注：%s</div>' % esc(m["review_note"]))

    parts.append('<form method="post" action="/admin/action" class="row" style="margin-top:10px">')
    parts.append('<input type="hidden" name="material_id" value="%s">' % esc(m["id"]))
    parts.append('<input class="grow" type="text" name="reason" placeholder="审核/操作备注（可空）">')
    for action, label, css in (
        ("approve", "通过", ""),
        ("reject", "拒绝", "ghost-danger"),
        ("remove", "下架", "ghost-danger"),
        ("restore", "恢复", "ghost"),
    ):
        parts.append('<button class="%s small-btn" type="submit" name="action" value="%s">%s</button>'
                     % (css, action, label))
    parts.append('<a class="btn ghost small-btn" href="/material/%s">查看</a>' % esc(m["id"]))
    parts.append('</form>')
    parts.append('</div>')
    return "".join(parts)


def render_about():
    parts = ['<h1>关于本站</h1>']
    parts.append(
        '<div class="card">'
        '<h2 style="margin-top:0">版权说明（占位文本）</h2>'
        '<p class="muted">本站是一个仅供本机使用的课程资料共享工具，用于同学之间交流学习资料。'
        '上传者应确保自己有权分享所上传的内容。若某份资料侵犯了你的权利，'
        '请通过下方的投诉通道联系我们，我们会尽快处理（下架仅修改状态，不删除文件）。</p>'
        '<h2>投诉通道（占位文本）</h2>'
        '<p class="muted">投诉邮箱：待填写<br>'
        '处理时限：待填写<br>'
        '本站不收集用户账号，也不对外网提供服务。</p>'
        '<h2>隐私说明</h2>'
        '<p class="muted">上传时会自动清除 PDF / Office 的作者、公司、修订信息，'
        '以及图片的 EXIF。IP 地址只以 HMAC 摘要形式保存，不保存明文。</p>'
        '</div>'
    )
    return layout("关于", "".join(parts), "about")
