export function esc(value) {
  if (value === null || value === undefined) {
    return "";
  }
  return String(value).replace(/[&<>"']/g, (char) => {
    switch (char) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      case "'":
        return "&#39;";
      default:
        return char;
    }
  });
}

export function qs(params) {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== "") {
      search.set(key, value);
    }
  }
  return search.toString();
}

export function htmlResponse(body, status = 200) {
  return new Response(body, {
    status,
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Cache-Control": "no-store",
    },
  });
}

export function redirectResponse(location, headers = {}) {
  return new Response(null, {
    status: 303,
    headers: {
      Location: location,
      ...headers,
    },
  });
}

const BASE_CSS = `
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
.badge.flag { background: #fdeaea; color: var(--bad); border: 1px solid #f5b5b5; margin-left: 4px; }
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
`;

const SUBMIT_FEEDBACK_JS = `
(function () {
  document.addEventListener("submit", function (e) {
    if (e.defaultPrevented) { return; }
    var button = e.submitter;
    if (!button || button.hasAttribute("name")) { return; }
    button.disabled = true;
    button.textContent = button.getAttribute("data-loading") || "提交中…";
  });
})();
`;

export function layout(title, body, active = "") {
  const navItem = (href, text, key) => {
    const klass = active === key ? ' class="active"' : "";
    return `<a href="${href}"${klass}>${text}</a>`;
  };

  return (
    "<!DOCTYPE html>\n<html lang=\"zh-CN\">\n<head>\n" +
    "<meta charset=\"utf-8\">\n" +
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n" +
    `<title>${esc(title)} · 课程资料共享</title>\n` +
    `<style>${BASE_CSS}</style>\n` +
    "</head>\n<body>\n" +
    "<header class=\"topbar\"><div class=\"wrap\">" +
    "<div class=\"brand\">课程资料<span>共享站</span></div>" +
    `<nav>${navItem("/", "首页", "home")} ${navItem("/upload", "上传资料", "upload")} ` +
    `${navItem("/admin", "管理页", "admin")} ${navItem("/about", "关于", "about")}</nav>` +
    "</div></header>\n" +
    `<main class="wrap">${body}</main>\n` +
    "<footer><strong>非官方学生项目，与澳门大学及任何院校无关。</strong>" +
    "本站不收费、不挂广告。" +
    '<a href="/about">免责声明与用户协议</a></footer>\n' +
    `<script>${SUBMIT_FEEDBACK_JS}</script>\n` +
    "</body></html>"
  );
}

export function flash(kind, text) {
  return `<div class="flash ${esc(kind)}">${esc(text)}</div>`;
}

function tagsHtml(tagsText) {
  if (!tagsText) {
    return "";
  }
  let tags;
  try {
    tags = JSON.parse(tagsText);
  } catch {
    return "";
  }
  if (!Array.isArray(tags)) {
    return "";
  }
  return tags.map((tag) => `<span class="tag">${esc(tag)}</span>`).join("");
}

function statusBadge(status) {
  const labels = {
    pending: "待审核",
    approved: "已通过",
    rejected: "已拒绝",
    removed: "已下架",
  };
  return `<span class="badge ${esc(status || "unknown")}">${esc(labels[status] || status || "未知")}</span>`;
}

export function renderHome(rows, totalCount, page, totalPages, q, courseCode, category, semester, options) {
  const parts = ["<h1>资料库</h1>"];
  parts.push('<form class="card" method="get" action="/">');
  parts.push('<div class="row">');
  parts.push(`<input class="grow" type="search" name="q" placeholder="搜索标题 / 课程代码 / 简介，回车或点按钮" value="${esc(q)}">`);
  parts.push('<button type="submit">搜索</button>');
  parts.push("</div>");
  parts.push('<div class="row" style="margin-top:10px">');
  parts.push('<div class="grow"><label class="field"><span class="label-text">课程代码</span>');
  parts.push(`<select name="course_code">${selectOptions(options.course_codes, courseCode, "全部课程")}</select></label></div>`);
  parts.push('<div class="grow"><label class="field"><span class="label-text">类别</span>');
  parts.push(`<select name="category">${selectOptions(options.categories, category, "全部类别")}</select></label></div>`);
  parts.push('<div class="grow"><label class="field"><span class="label-text">学期</span>');
  parts.push(`<select name="semester">${selectOptions(options.semesters, semester, "全部学期")}</select></label></div>`);
  parts.push("</div>");
  parts.push('<div class="row"><button type="submit">应用筛选</button><a class="btn ghost" href="/">清空条件</a></div>');
  parts.push("</form>");

  if (rows.length) {
    parts.push(`<p class="muted small">共找到 ${totalCount} 条资料，第 ${page} / ${totalPages} 页。</p>`);
  } else {
    parts.push(`<p class="muted small">共找到 ${totalCount} 条资料。</p>`);
  }

  if (!rows.length) {
    const text = q || courseCode || category || semester
      ? "没有符合条件的资料。试试换一个关键词，或者点“清空条件”。"
      : "资料库现在还是空的。你可以点上方“上传资料”来添加第一份。";
    parts.push(`<div class="card empty">${esc(text)}</div>`);
  } else {
    for (const row of rows) {
      let description = row.description || "（没有填写简介）";
      if (description.length > 130) {
        description = description.slice(0, 130) + "…";
      }
      parts.push(
        '<div class="card">' +
        `<h2 style="margin-top:0"><a href="/material/${esc(row.id)}">${esc(row.title)}</a></h2>` +
        `<div class="muted small">${esc(row.course_code || "未填课程代码")} · ` +
        `${esc(row.category || "未分类")} · ${esc(row.semester || "未填学期")} · ` +
        `上传于 ${esc((row.created_at || "").slice(0, 10))}</div>` +
        `<p>${esc(description)}</p>` +
        `<div>${tagsHtml(row.tags)}</div>` +
        `<div class="muted small">下载 ${row.downloads || 0} 次 · 浏览 ${row.views || 0} 次</div>` +
        "</div>",
      );
    }
  }

  if (totalPages > 1) {
    const base = {
      q,
      course_code: courseCode,
      category,
      semester,
    };
    parts.push('<div class="pager">');
    parts.push(page > 1
      ? `<a href="/?${qs({ page: page - 1, ...base })}">上一页</a>`
      : '<span class="muted small">上一页</span>');
    parts.push(`<span class="current">${page}</span>`);
    parts.push(`<span class="muted small">共 ${totalPages} 页</span>`);
    parts.push(page < totalPages
      ? `<a href="/?${qs({ page: page + 1, ...base })}">下一页</a>`
      : '<span class="muted small">下一页</span>');
    parts.push("</div>");
  }

  return layout("资料库", parts.join(""), "home");
}

function selectOptions(values, selected, allLabel) {
  const out = [`<option value="">${esc(allLabel)}</option>`];
  for (const value of values) {
    const mark = value === selected ? " selected" : "";
    out.push(`<option value="${esc(value)}"${mark}>${esc(value)}</option>`);
  }
  return out.join("");
}

const UPLOAD_FORM_JS = `
(function () {
  var zone = document.getElementById("dropzone");
  var input = document.getElementById("file-input");
  var nameBox = document.getElementById("file-name");
  var errorBox = document.getElementById("client-error");
  var allowed = ["pdf","docx","pptx","xlsx","zip","png","jpg","jpeg","md","txt","epub"];
  var maxBytes = 2 * 1024 * 1024;

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
      showError("文件太大：" + (file.size / 1024 / 1024).toFixed(1) + " MB，上限 2 MB。");
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
`;

export function renderUpload(error = null, values = {}, duplicate = null) {
  values = values || {};
  const parts = ["<h1>上传资料</h1>"];
  if (error) {
    parts.push(flash("bad", error));
  }
  if (duplicate) {
    parts.push(
      '<div class="flash info">这个文件已经有人上传过，没有重复保存。' +
      `原资料链接：<a href="/material/${esc(duplicate.id)}">${esc(duplicate.title)}</a></div>`,
    );
  }

  parts.push(
    '<div class="flash info">上传后资料进入“待审核”状态，不会马上公开。' +
    '单个文件不超过 2 MB。系统会自动清除文档和图片里的作者 / 公司 / EXIF 等元数据。</div>',
  );

  const categories = ["笔记", "真题", "课件", "教材", "其他"];
  const categorySelected = values.category || "";
  const categoryOptions = ['<option value="">请选择</option>'];
  for (const item of categories) {
    const mark = item === categorySelected ? " selected" : "";
    categoryOptions.push(`<option value="${esc(item)}"${mark}>${esc(item)}</option>`);
  }

  parts.push('<form id="upload-form" class="card" method="post" action="/upload" enctype="multipart/form-data">');
  parts.push('<div id="client-error" class="flash bad" style="display:none"></div>');
  parts.push(
    '<div id="dropzone" class="dropzone">把文件拖到这里，或者点这里选择文件<br>' +
    '<span class="small">pdf / docx / pptx / xlsx / zip / png / jpg / md / txt / epub，≤ 2 MB</span></div>',
  );
  parts.push(
    '<input id="file-input" type="file" name="file" style="display:none" ' +
    'accept=".pdf,.docx,.pptx,.xlsx,.zip,.png,.jpg,.jpeg,.md,.txt,.epub">',
  );
  parts.push('<div id="file-name" class="small muted" style="margin:8px 0 14px"></div>');

  parts.push(`<label class="field"><span class="label-text">标题（必填）</span><input type="text" name="title" required value="${esc(values.title || "")}"></label>`);
  parts.push('<div class="row">');
  parts.push(`<div class="grow"><label class="field"><span class="label-text">课程代码</span><input type="text" name="course_code" placeholder="例如 ECEN1010" value="${esc(values.course_code || "")}"></label></div>`);
  parts.push(`<div class="grow"><label class="field"><span class="label-text">课程名称</span><input type="text" name="course_name" value="${esc(values.course_name || "")}"></label></div>`);
  parts.push("</div>");
  parts.push('<div class="row">');
  parts.push(`<div class="grow"><label class="field"><span class="label-text">类别</span><select name="category">${categoryOptions.join("")}</select></label></div>`);
  parts.push(`<div class="grow"><label class="field"><span class="label-text">学期</span><input type="text" name="semester" placeholder="例如 2026S1" value="${esc(values.semester || "")}"></label></div>`);
  parts.push("</div>");
  parts.push(`<label class="field"><span class="label-text">标签（用逗号分隔）</span><input type="text" name="tags" placeholder="例如 期末,重点,公式" value="${esc(values.tags || "")}"></label>`);
  parts.push(`<label class="field"><span class="label-text">简介</span><textarea name="description">${esc(values.description || "")}</textarea></label>`);
  parts.push(`<label class="field"><span class="label-text">上传者昵称（可空，别人能看到）</span><input type="text" name="uploader_note" value="${esc(values.uploader_note || "")}"></label>`);
  parts.push('<button type="submit">提交上传</button>');
  parts.push("</form>");
  parts.push(`<script>${UPLOAD_FORM_JS}</script>`);
  return layout("上传资料", parts.join(""), "upload");
}

export function renderMaterial(material) {
  const parts = [`<h1>${esc(material.title)}</h1>`];
  parts.push('<div class="card">');
  parts.push(`<p>${esc(material.description || "（没有填写简介）")}</p>`);
  parts.push(`<div>${tagsHtml(material.tags)}</div>`);
  parts.push('<div class="meta-grid">');
  const rows = [
    ["课程代码", material.course_code],
    ["课程名称", material.course_name],
    ["类别", material.category],
    ["学期", material.semester],
    ["规范文件名", material.file_name],
    ["文件大小", humanSize(material.file_size)],
    ["文件类型", material.mime_type],
    ["上传者昵称", material.uploader_note],
    ["上传时间", material.created_at],
    ["下载次数", String(material.downloads || 0)],
    ["浏览次数", String(material.views || 0)],
  ];
  for (const [key, value] of rows) {
    parts.push(`<div class="k">${esc(key)}</div><div>${esc(value === null || value === undefined || value === "" ? "—" : value)}</div>`);
  }
  parts.push("</div>");
  parts.push(`<div class="row" style="margin-top:16px"><a class="btn" href="/download/${esc(material.id)}">下载文件</a></div>`);
  parts.push("</div>");

  parts.push('<div class="card">');
  parts.push('<h2 style="margin-top:0">举报这份资料</h2>');
  parts.push(
    '<form method="post" action="/report">' +
    `<input type="hidden" name="material_id" value="${esc(material.id)}">` +
    '<label class="field"><span class="label-text">原因</span>' +
    '<select name="reason">' +
    '<option value="侵权">侵权</option>' +
    '<option value="内容错误">内容错误</option>' +
    '<option value="无法下载">无法下载</option>' +
    '<option value="其他">其他</option>' +
    "</select></label>" +
    '<label class="field"><span class="label-text">补充说明（可空）</span><textarea name="detail"></textarea></label>' +
    '<button class="ghost-danger" type="submit">提交举报</button>' +
    "</form>" +
    '<p class="small muted">同一份资料累计 3 条未处理举报会自动下架，文件不会删除。</p>',
  );
  parts.push("</div>");
  return layout(material.title, parts.join(""), "home");
}

export function renderMessage(title, text, links = null) {
  const parts = [`<h1>${esc(title)}</h1>`];
  parts.push(`<div class="card"><p>${esc(text)}</p>`);
  if (links && links.length) {
    parts.push('<div class="row">');
    for (const [href, label] of links) {
      parts.push(`<a class="btn ghost" href="${esc(href)}">${esc(label)}</a>`);
    }
    parts.push("</div>");
  }
  parts.push("</div>");
  return layout(title, parts.join(""));
}

export function renderAdminLogin(error = null) {
  const parts = ["<h1>管理页登录</h1>"];
  if (error) {
    parts.push(flash("bad", error));
  }
  parts.push(
    '<div class="card">' +
    '<p class="muted">管理令牌从环境变量 ADMIN_TOKEN 读取。本地开发请写在 .dev.vars 中。</p>' +
    '<form method="post" action="/admin">' +
    '<label class="field"><span class="label-text">管理令牌</span>' +
    '<input type="password" name="token" autocomplete="current-password"></label>' +
    '<button type="submit">进入管理页</button>' +
    "</form></div>",
  );
  return layout("管理页登录", parts.join(""), "admin");
}

export function renderAdmin(materials, reports, counts, intercepts = []) {
  const parts = ["<h1>管理页</h1>"];
  parts.push(
    '<div class="row">' +
    `<span class="badge pending">待审核 ${counts.pending || 0}</span>` +
    `<span class="badge approved">已通过 ${counts.approved || 0}</span>` +
    `<span class="badge rejected">已拒绝 ${counts.rejected || 0}</span>` +
    `<span class="badge removed">已下架 ${counts.removed || 0}</span>` +
    `<span class="badge">未处理举报 ${counts.open_reports || 0}</span>` +
    '<a class="btn ghost small-btn" href="/admin/logout">退出登录</a>' +
    "</div>",
  );

  parts.push("<h2>举报列表</h2>");
  if (!reports.length) {
    parts.push('<div class="card empty">目前没有举报。</div>');
  } else {
    parts.push('<div class="card"><table><tr><th>时间</th><th>资料</th><th>原因</th><th>说明</th><th>状态</th><th>操作</th></tr>');
    for (const report of reports) {
      parts.push(
        `<tr><td class="small">${esc((report.created_at || "").slice(0, 16))}</td>` +
        `<td><a href="/material/${esc(report.material_id)}">${esc(report.material_title || report.material_id)}</a></td>` +
        `<td>${esc(report.reason)}</td><td class="small">${esc(report.detail)}</td>` +
        `<td>${esc(report.status)}</td>` +
        `<td>${report.status === "open" ? reportActionForm(report.id) : ""}</td></tr>`,
      );
    }
    parts.push("</table></div>");
  }

  parts.push("<h2>拦截记录</h2>");
  if (!intercepts.length) {
    parts.push('<div class="card empty">目前没有被系统拒绝的上传记录。</div>');
  } else {
    parts.push('<div class="card"><table><tr><th>时间</th><th>规则</th></tr>');
    for (const item of intercepts) {
      parts.push(
        `<tr><td class="small">${esc((item.created_at || "").slice(0, 16))}</td>` +
        `<td>${esc(item.rule)}</td></tr>`,
      );
    }
    parts.push("</table></div>");
  }

  parts.push("<h2>资料列表</h2>");
  if (!materials.length) {
    parts.push('<div class="card empty">还没有任何资料。</div>');
  } else {
    for (const material of materials) {
      parts.push(adminMaterialCard(material));
    }
  }

  return layout("管理页", parts.join(""), "admin");
}

function reportActionForm(reportId) {
  return (
    '<form method="post" action="/admin/action">' +
    '<input type="hidden" name="action" value="handle_report">' +
    `<input type="hidden" name="report_id" value="${esc(reportId)}">` +
    '<button class="ghost small-btn" type="submit">标记已处理</button>' +
    "</form>"
  );
}

function adminMaterialCard(material) {
  const flag = material.intercept_flag
    ? `<span class="badge flag">预检标记：${esc(interceptLabel(material.intercept_flag))}</span>`
    : "";
  const parts = ['<div class="card">'];
  parts.push(`<div class="row"><strong class="grow">${esc(material.title)}</strong>${statusBadge(material.status)}${flag}</div>`);
  parts.push(
    `<div class="small muted">ID ${esc(material.id)} · ${esc(material.course_code || "无课程代码")} · ` +
    `${esc(material.category || "未分类")} · ${esc(material.semester || "无学期")} · ` +
    `上传时间 ${esc((material.created_at || "").slice(0, 16))}</div>`,
  );
  parts.push(`<div class="small muted">原始文件名（仅管理员可见）：${esc(material.original_name)}</div>`);
  parts.push(
    `<div class="small muted">规范文件名：${esc(material.file_name)} · ${humanSize(material.file_size)} · ` +
    `举报数 ${material.report_count || 0}</div>`,
  );
  if (material.review_note) {
    parts.push(`<div class="small">审核备注：${esc(material.review_note)}</div>`);
  }

  parts.push('<form method="post" action="/admin/action" class="row" style="margin-top:10px">');
  parts.push(`<input type="hidden" name="material_id" value="${esc(material.id)}">`);
  parts.push('<input class="grow" type="text" name="reason" placeholder="审核/操作备注（可空）">');
  for (const [action, label, css] of [
    ["approve", "通过", ""],
    ["reject", "拒绝", "ghost-danger"],
    ["remove", "下架", "ghost-danger"],
    ["restore", "恢复", "ghost"],
  ]) {
    parts.push(`<button class="${css} small-btn" type="submit" name="action" value="${action}">${label}</button>`);
  }
  parts.push(`<a class="btn ghost small-btn" href="/material/${esc(material.id)}">查看</a>`);
  parts.push("</form>");
  parts.push("</div>");
  return parts.join("");
}

function interceptLabel(rule) {
  if (rule === "channel:archive") {
    return "压缩包";
  }
  if (rule === "channel:image") {
    return "图片";
  }
  if (rule === "channel:text") {
    return "纯文本";
  }
  if (String(rule || "").startsWith("keyword:")) {
    return "关键词";
  }
  return rule || "未知";
}

function humanSize(size) {
  if (size === null || size === undefined) {
    return "—";
  }
  let value = Number(size);
  for (const unit of ["B", "KB", "MB", "GB"]) {
    if (value < 1024 || unit === "GB") {
      return unit === "B" ? `${Math.trunc(value)} B` : `${value.toFixed(1)} ${unit}`;
    }
    value /= 1024;
  }
  return "—";
}

export function renderAbout() {
  const parts = ["<h1>关于本站</h1>"];
  parts.push(
    '<div class="card">' +
    '<h2 style="margin-top:0">非官方声明</h2>' +
    '<p class="muted">本站是一个学生自发的个人兴趣项目，与澳门大学及任何院校、' +
    "任何校内组织（包括但不限于学生会、书院、社团）均无隶属关系，" +
    "未获其授权、认可或支持，不代表其立场。本站不使用任何院校的名称、校徽、标识。" +
    "本站由非专业团队维护，能力有限，尽力而为；服务可能中断、可能出错、" +
    "可能随时调整或停止。</p>" +

    "<h2>关于资料的权利</h2>" +
    '<p class="muted">本站开源的是<strong>代码和资料信息</strong>，不是资料本身。' +
    "用户上传的资料，著作权仍属于原作者或上传者，不因上传到本站而转移或放弃。" +
    "<strong>上传者需自行确保有权分享所上传的内容。</strong></p>" +
    '<p class="muted">「免费」指本站不向任何人收费，不指向上传者或权利人收取任何形式的' +
    "授权费，也不代表本站可以替权利人放弃其权利。</p>" +

    "<h2>上传规则</h2>" +
    '<p class="muted">可以上传与课程学习相关的笔记、往年试题、课件、教材等；' +
    "<strong>不要</strong>上传：违反法律法规的内容、含他人隐私的文件、" +
    "标注「勿外传」「仅内部」或来源不明的加密文件、与学习无关的广告推广、" +
    "以及恶意文件。</p>" +
    '<p class="muted"><strong>请注意</strong>：本站会在上传时自动清除文件的作者、公司、' +
    "修订记录、图片定位等元数据，但<strong>正文里的姓名、学号等不会被自动清除</strong>——" +
    "请不要上传正文含他人隐私信息的文件。</p>" +

    "<h2>投诉与举报</h2>" +
    '<p class="muted">认为某份资料侵犯了你的权益，请用该资料页上的「举报」按钮提交，' +
    "可在说明栏写明你的具体主张。<br>" +
    "处理时限：<strong>48 小时内</strong>。<br>" +
    "处理方式默认为「下架」而非「删除」：资料不再公开、不可搜索和下载，" +
    "但文件本身不删除——这样处理可逆，投诉不成立时可以恢复发布。</p>" +
    '<p class="muted">举报表单不要求填写联系方式，本站也不主动索取，' +
    "并且<strong>不保证回复</strong>。若希望我们处理后回复你，可在说明栏自愿留下联系方式。</p>" +

    "<h2>隐私与匿名</h2>" +
    '<p class="muted">本站不注册、不登录、不收邮箱、不收密码。' +
    "IP 地址不保存明文，仅以带密钥的摘要形式保存，用于防滥用，不可反查。</p>" +
    '<p class="muted">因此<strong>本站无法识别上传者是谁，也无法替你找回「你的」上传记录</strong>' +
    "——这不是推脱，是没有身份可以对应。请自行保存上传过的资料副本。</p>" +

    "<h2>本站的承诺</h2>" +
    '<p class="muted">① 资料永久免费：不收费、不挂广告、不做会员、不设下载门槛；' +
    "② 平台代码开源，任何人可以自建一份；" +
    "③ 信息开放可迁移：上传者随时可以要求取回自己上传的资料。</p>" +
    "</div>",
  );
  return layout("关于", parts.join(""), "about");
}
