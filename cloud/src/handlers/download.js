import { first, run, nowText } from "../db.js";
import { createStorage } from "../storage.js";
import { renderMessage, htmlResponse } from "../pages.js";

export async function handleDownload(request, env, routeParam) {
  const param = decodeURIComponent(String(routeParam || "").trim());
  if (!param) {
    return htmlResponse(renderMessage(
      "无法下载",
      "缺少资料编号。",
      [["/", "回到首页"]],
    ), 404);
  }

  let material = await first(env.DB, "SELECT * FROM materials WHERE id = ?", [param]);
  if (!material) {
    material = await first(env.DB, "SELECT * FROM materials WHERE file_key = ?", [param]);
  }
  if (!material || material.status !== "approved") {
    return htmlResponse(renderMessage(
      "无法下载",
      "这份资料不存在，或者还没有通过审核。",
      [["/", "回到首页"]],
    ), 404);
  }

  const storage = createStorage(env);
  const body = await storage.get(material.file_key);
  if (!body) {
    return htmlResponse(renderMessage(
      "文件不见了",
      "数据库里有记录，但对象存储里找不到文件。请联系管理员。",
      [["/", "回到首页"]],
    ), 404);
  }

  await run(
    env.DB,
    "UPDATE materials SET downloads = downloads + 1, updated_at = ? WHERE id = ?",
    [nowText(), material.id],
  );

  const fileName = material.file_name || `${material.id}.bin`;
  return new Response(body, {
    status: 200,
    headers: {
      "Content-Type": material.mime_type || "application/octet-stream",
      "Content-Length": String(material.file_size || ""),
      "Content-Disposition": contentDisposition(fileName),
      "Cache-Control": "no-store",
    },
  });
}

function contentDisposition(fileName) {
  const fallback = String(fileName || "material.bin")
    .replace(/[^\x20-\x7e]/g, "_")
    .replace(/["\\]/g, "_") || "material.bin";
  const encoded = encodeURIComponent(fileName).replace(/['()]/g, (char) => {
    return `%${char.charCodeAt(0).toString(16).toUpperCase()}`;
  });
  return `attachment; filename="${fallback}"; filename*=UTF-8''${encoded}`;
}
