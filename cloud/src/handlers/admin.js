import { all, first, run, newId, nowText } from "../db.js";
import { sha256Hex } from "../storage.js";
import { renderAdminLogin, renderAdmin, renderMessage, htmlResponse, redirectResponse } from "../pages.js";

export async function handleAdminPage(request, env) {
  if (!(await isAdmin(request, env))) {
    const url = new URL(request.url);
    const token = url.searchParams.get("token") || "";
    return htmlResponse(renderAdminLogin(token ? "令牌不对，请重新输入。" : null), token ? 401 : 200);
  }

  const counts = {
    pending: 0,
    approved: 0,
    rejected: 0,
    removed: 0,
    open_reports: 0,
  };
  const countRows = await all(env.DB, "SELECT status, COUNT(*) AS c FROM materials GROUP BY status");
  for (const row of countRows) {
    if (Object.prototype.hasOwnProperty.call(counts, row.status)) {
      counts[row.status] = Number(row.c || 0);
    }
  }
  const reportCount = await first(env.DB, "SELECT COUNT(*) AS c FROM reports WHERE status = 'open'");
  counts.open_reports = Number(reportCount?.c || 0);

  const materials = await all(
    env.DB,
    "SELECT m.*, (SELECT COUNT(*) FROM reports r WHERE r.material_id = m.id AND r.status='open') " +
    "AS report_count FROM materials m " +
    "ORDER BY CASE m.status WHEN 'pending' THEN 0 ELSE 1 END, m.created_at DESC",
  );
  const reports = await all(
    env.DB,
    "SELECT r.*, m.title AS material_title FROM reports r " +
    "LEFT JOIN materials m ON m.id = r.material_id " +
    "ORDER BY CASE r.status WHEN 'open' THEN 0 ELSE 1 END, r.created_at DESC",
  );
  const intercepts = await all(
    env.DB,
    "SELECT created_at, rule FROM intercept_log WHERE action = 'rejected' ORDER BY created_at DESC LIMIT 20",
  );

  return htmlResponse(renderAdmin(materials, reports, counts, intercepts));
}

export async function handleAdminLogin(request, env) {
  const form = await request.formData();
  const token = stringValue(form.get("token")).trim();
  const expected = String(env.ADMIN_TOKEN || "");
  if (token && timingSafeEqual(token, expected)) {
    const cookieValue = await sha256Hex(new TextEncoder().encode(expected));
    return redirectResponse("/admin", {
      "Set-Cookie": `ldsg_admin=${cookieValue}; Path=/; HttpOnly; SameSite=Lax`,
    });
  }
  return htmlResponse(renderAdminLogin("令牌不对，请重新输入。"), 401);
}

export function handleAdminLogout() {
  return redirectResponse("/admin", {
    "Set-Cookie": "ldsg_admin=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax",
  });
}

export async function handleAdminAction(request, env) {
  if (!(await isAdmin(request, env))) {
    return htmlResponse(renderAdminLogin("登录状态已失效，请重新输入令牌。"), 401);
  }

  const form = await request.formData();
  const action = stringValue(form.get("action")).trim();
  const materialId = stringValue(form.get("material_id")).trim();
  const reason = stringValue(form.get("reason")).trim();
  const actor = "admin";
  const createdAt = nowText();

  const statusMap = {
    approve: "approved",
    reject: "rejected",
    remove: "removed",
    restore: "approved",
  };

  if (action === "handle_report") {
    const reportId = stringValue(form.get("report_id")).trim();
    const report = await first(env.DB, "SELECT * FROM reports WHERE id = ?", [reportId]);
    if (!report) {
      return htmlResponse(renderMessage("操作失败", "找不到这条举报。", [["/admin", "回管理页"]]), 404);
    }
    await run(env.DB, "UPDATE reports SET status = 'handled' WHERE id = ?", [reportId]);
    await run(
      env.DB,
      "INSERT INTO audit_log (id, material_id, action, reason, actor, created_at) VALUES (?,?,?,?,?,?)",
      [newId(), report.material_id, "handle_report", reason || "标记举报已处理", actor, createdAt],
    );
  } else if (Object.prototype.hasOwnProperty.call(statusMap, action)) {
    if (!materialId) {
      return htmlResponse(renderMessage("操作失败", "缺少资料编号。", [["/admin", "回管理页"]]), 400);
    }
    const row = await first(env.DB, "SELECT id FROM materials WHERE id = ?", [materialId]);
    if (!row) {
      return htmlResponse(renderMessage("操作失败", "找不到这份资料。", [["/admin", "回管理页"]]), 404);
    }
    await run(
      env.DB,
      "UPDATE materials SET status=?, review_note=?, reviewed_at=?, reviewer=?, updated_at=? WHERE id=?",
      [statusMap[action], reason, createdAt, actor, createdAt, materialId],
    );
    await run(
      env.DB,
      "INSERT INTO audit_log (id, material_id, action, reason, actor, created_at) VALUES (?,?,?,?,?,?)",
      [newId(), materialId, action, reason, actor, createdAt],
    );
  } else {
    return htmlResponse(renderMessage("操作失败", `不认识的操作：${action}。`, [["/admin", "回管理页"]]), 400);
  }

  return redirectResponse("/admin");
}

async function isAdmin(request, env) {
  const expected = String(env.ADMIN_TOKEN || "");
  if (!expected) {
    return false;
  }
  const token = new URL(request.url).searchParams.get("token") || "";
  if (token && timingSafeEqual(token, expected)) {
    return true;
  }
  const cookie = parseCookie(request.headers.get("Cookie") || "", "ldsg_admin");
  if (!cookie) {
    return false;
  }
  const expectedCookie = await sha256Hex(new TextEncoder().encode(expected));
  return timingSafeEqual(cookie, expectedCookie);
}

function parseCookie(raw, name) {
  for (const piece of raw.split(";")) {
    const index = piece.indexOf("=");
    if (index < 0) {
      continue;
    }
    const key = piece.slice(0, index).trim();
    if (key === name) {
      return piece.slice(index + 1).trim();
    }
  }
  return "";
}

function timingSafeEqual(left, right) {
  const a = String(left || "");
  const b = String(right || "");
  const length = Math.max(a.length, b.length);
  let diff = a.length ^ b.length;
  for (let index = 0; index < length; index += 1) {
    diff |= (a.charCodeAt(index) || 0) ^ (b.charCodeAt(index) || 0);
  }
  return diff === 0;
}

function stringValue(value) {
  return typeof value === "string" ? value : "";
}
