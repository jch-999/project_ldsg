import { first, run, newId, nowText } from "../db.js";
import { ipHmac } from "../preflight.js";
import { renderMessage, htmlResponse } from "../pages.js";

const REPORT_LIMIT = 3;

export async function handleReport(request, env) {
  const form = await request.formData();
  const materialId = stringValue(form.get("material_id")).trim();
  const reason = stringValue(form.get("reason")).trim() || "其他";
  const detail = stringValue(form.get("detail")).trim();

  if (!materialId) {
    return htmlResponse(renderMessage("举报失败", "缺少资料编号。", [["/", "回到首页"]]), 400);
  }

  const material = await first(
    env.DB,
    "SELECT id, title, status FROM materials WHERE id = ?",
    [materialId],
  );
  if (!material) {
    return htmlResponse(renderMessage("举报失败", "这份资料不存在。", [["/", "回到首页"]]), 404);
  }

  const createdAt = nowText();
  await run(
    env.DB,
    "INSERT INTO reports (id, material_id, reason, detail, ip_hmac, status, created_at) VALUES (?,?,?,?,?,?,?)",
    [newId(), materialId, reason, detail, await ipHmac(request, env), "open", createdAt],
  );

  const countRow = await first(
    env.DB,
    "SELECT COUNT(*) AS c FROM reports WHERE material_id = ? AND status = 'open'",
    [materialId],
  );
  const openCount = Number(countRow?.c || 0);
  let autoRemoved = false;

  if (openCount >= REPORT_LIMIT && material.status !== "removed") {
    await run(
      env.DB,
      "UPDATE materials SET status='removed', review_note=?, reviewed_at=?, reviewer=?, updated_at=? WHERE id=?",
      [
        `未处理举报累计达到 ${REPORT_LIMIT} 次，系统自动下架`,
        createdAt,
        "system",
        createdAt,
        materialId,
      ],
    );
    await run(
      env.DB,
      "INSERT INTO audit_log (id, material_id, action, reason, actor, created_at) VALUES (?,?,?,?,?,?)",
      [
        newId(),
        materialId,
        "auto_remove",
        `未处理举报累计达到 ${REPORT_LIMIT} 次`,
        "system",
        createdAt,
      ],
    );
    autoRemoved = true;
  }

  const extra = autoRemoved
    ? `该资料的未处理举报已达到 ${REPORT_LIMIT} 次，系统已自动将其下架。`
    : "";
  return htmlResponse(renderMessage(
    "举报已提交",
    `谢谢，你的举报已经记录。管理员会尽快处理。${extra}`,
    [["/", "回到首页"], [`/material/${materialId}`, "返回资料页"]],
  ));
}

function stringValue(value) {
  return typeof value === "string" ? value : "";
}
