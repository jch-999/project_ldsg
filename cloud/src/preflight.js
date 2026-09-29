// 高危关键词表（第一版留空，等咨询后填入）。
// TODO: 待填入。填入前，这一项不生效。
export const BLOCKED_KEYWORDS = [
];

// 通道分流：这些类型强制人审（不自动放行）。
export const FORCE_REVIEW_CHANNELS = {
  ".zip": "压缩包可藏任意内容",
  ".png": "图片可藏内容",
  ".jpg": "图片可藏内容",
  ".jpeg": "图片可藏内容",
  ".txt": "纯文本",
  ".md": "纯文本",
};

const CHANNEL_RULES = {
  ".zip": "channel:archive",
  ".png": "channel:image",
  ".jpg": "channel:image",
  ".jpeg": "channel:image",
  ".txt": "channel:text",
  ".md": "channel:text",
};

export function extensionOf(filename) {
  const name = String(filename || "");
  const dot = name.lastIndexOf(".");
  return dot >= 0 ? name.slice(dot).toLowerCase() : "";
}

export function preflight({ filename, mime, size, bytes, title, description, courseCode }) {
  const haystack = [filename, title, description, courseCode]
    .filter((value) => value !== null && value !== undefined)
    .join("\n")
    .toLowerCase();

  for (const rawKeyword of BLOCKED_KEYWORDS) {
    const keyword = String(rawKeyword || "").trim();
    if (!keyword) {
      continue;
    }
    if (haystack.includes(keyword.toLowerCase())) {
      return { decision: "reject", rule: `keyword:${keyword}` };
    }
  }

  const ext = extensionOf(filename);
  if (Object.prototype.hasOwnProperty.call(FORCE_REVIEW_CHANNELS, ext)) {
    return {
      decision: "flag",
      rule: CHANNEL_RULES[ext] || `channel:${ext.replace(".", "")}`,
    };
  }

  return { decision: "allow" };
}

export async function ipHmac(request, env) {
  const keyText = String(env.IP_HMAC_KEY || "");
  if (!keyText) {
    throw new Error("缺少 IP_HMAC_KEY 环境变量");
  }
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(keyText),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(clientIp(request)),
  );
  return [...new Uint8Array(signature)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function clientIp(request) {
  const direct = request.headers.get("CF-Connecting-IP") || request.headers.get("X-Real-IP");
  if (direct) {
    return direct.trim();
  }
  const forwarded = request.headers.get("X-Forwarded-For") || "";
  return forwarded.split(",")[0].trim() || "127.0.0.1";
}
