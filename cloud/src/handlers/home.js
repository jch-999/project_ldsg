import { all, first, run } from "../db.js";
import { renderHome, renderMaterial, renderMessage, htmlResponse } from "../pages.js";

const PAGE_SIZE = 20;

export async function handleHome(request, env) {
  const url = new URL(request.url);
  const q = (url.searchParams.get("q") || "").trim();
  const courseCode = (url.searchParams.get("course_code") || "").trim();
  const category = (url.searchParams.get("category") || "").trim();
  const semester = (url.searchParams.get("semester") || "").trim();

  let page = Number.parseInt(url.searchParams.get("page") || "1", 10);
  if (!Number.isFinite(page) || page < 1) {
    page = 1;
  }

  const where = ["status = 'approved'"];
  const params = [];
  if (q) {
    where.push("(title LIKE ? OR course_code LIKE ? OR description LIKE ?)");
    const like = `%${q}%`;
    params.push(like, like, like);
  }
  if (courseCode) {
    where.push("course_code = ?");
    params.push(courseCode);
  }
  if (category) {
    where.push("category = ?");
    params.push(category);
  }
  if (semester) {
    where.push("semester = ?");
    params.push(semester);
  }

  const whereSql = where.join(" AND ");
  const countRow = await first(env.DB, `SELECT COUNT(*) AS c FROM materials WHERE ${whereSql}`, params);
  const totalCount = Number(countRow?.c || 0);
  const totalPages = Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
  if (page > totalPages) {
    page = totalPages;
  }

  const rows = await all(
    env.DB,
    `SELECT * FROM materials WHERE ${whereSql} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?`,
    [...params, PAGE_SIZE, (page - 1) * PAGE_SIZE],
  );

  const options = {
    course_codes: await distinctValues(env.DB, "course_code"),
    categories: await distinctValues(env.DB, "category"),
    semesters: await distinctValues(env.DB, "semester"),
  };

  return htmlResponse(renderHome(rows, totalCount, page, totalPages, q, courseCode, category, semester, options));
}

export async function handleMaterial(request, env, materialId) {
  const id = String(materialId || "").trim();
  let row = await first(env.DB, "SELECT * FROM materials WHERE id = ?", [id]);
  if (!row) {
    return htmlResponse(renderMessage(
      "资料不存在",
      "没有找到这份资料，链接可能已经失效。",
      [["/", "回到首页"]],
    ), 404);
  }

  if (row.status !== "approved") {
    const statusText = {
      pending: "这份资料正在等待管理员审核，通过后才会公开。",
      rejected: "这份资料没有通过审核，暂时不可查看。",
      removed: "这份资料已被下架，文件仍保存在对象存储中，管理员可以恢复。",
    }[row.status] || "这份资料当前不可查看。";
    return htmlResponse(renderMessage(
      "资料当前不可查看",
      statusText,
      [["/", "回到首页"], ["/upload", "上传资料"]],
    ));
  }

  await run(env.DB, "UPDATE materials SET views = views + 1 WHERE id = ?", [id]);
  row = await first(env.DB, "SELECT * FROM materials WHERE id = ?", [id]);
  return htmlResponse(renderMaterial(row));
}

async function distinctValues(db, column) {
  const allowed = new Set(["course_code", "category", "semester"]);
  if (!allowed.has(column)) {
    throw new Error(`不允许的筛选字段：${column}`);
  }
  const rows = await all(
    db,
    `SELECT DISTINCT ${column} AS v FROM materials ` +
    `WHERE status = 'approved' AND ${column} IS NOT NULL AND ${column} <> '' ORDER BY v`,
  );
  return rows.map((row) => row.v);
}

export { PAGE_SIZE };
