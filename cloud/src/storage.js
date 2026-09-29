export class Storage {
  async put(key, bytes, meta) {
    throw new Error("Storage.put 未实现");
  }

  async get(key) {
    throw new Error("Storage.get 未实现");
  }

  async list(prefix) {
    throw new Error("Storage.list 未实现");
  }

  async url(key) {
    throw new Error("Storage.url 未实现");
  }
}

export class R2Storage extends Storage {
  constructor(bucket) {
    super();
    this.bucket = bucket;
  }

  async put(key, bytes, meta = {}) {
    const size = byteLength(bytes);
    const sha256 = await sha256Hex(bytes);
    await this.bucket.put(key, bytes, {
      httpMetadata: meta.httpMetadata || {},
      customMetadata: meta.customMetadata || {},
    });
    return { provider: "r2", objectKey: key, size, sha256 };
  }

  async get(key) {
    const object = await this.bucket.get(key);
    if (!object) {
      return null;
    }
    return object.body;
  }

  async list(prefix = "") {
    const objects = [];
    let cursor = undefined;
    do {
      const page = await this.bucket.list({ prefix, cursor });
      for (const object of page.objects || []) {
        objects.push({
          key: object.key,
          size: object.size,
          uploaded: object.uploaded,
        });
      }
      cursor = page.truncated ? page.cursor : undefined;
    } while (cursor);
    return objects;
  }

  async url(key) {
    return `/download/${encodeURIComponent(key)}`;
  }
}

// 将来增加第二个存储源（例如 GitHub Releases、另一个 R2 桶）时，
// 只需要新增一个 Storage 实现类，并在工厂里按配置选择；业务代码不需要改。

/**
 * D1Storage —— 把文件字节直接存进 D1 的 files 表。
 *
 * 用途：R2 需要绑定信用卡才能开通，在拿到可用支付方式前，用 D1 顶替，
 *       让站点先能上线运行。这是**临时方案**，不是最终形态。
 *
 * 硬限制（Cloudflare 官方，Free 套餐）：
 *   - 单个 BLOB / 单行 最大 2,000,000 字节（2 MB）—— 超出写入直接失败
 *   - 免费版单库上限 500 MB（账号总存储 5 GB）
 * 因此应用层上传上限已下调至 2 MB（见 upload.js 的 MAX_FILE_SIZE）。
 *
 * 迁移到 R2/其他源时：把 createStorage 的判断改掉即可，业务代码零改动。
 */
export class D1Storage extends Storage {
  constructor(db) {
    super();
    this.db = db;
  }

  async put(key, bytes, meta = {}) {
    const size = byteLength(bytes);
    const sha256 = await sha256Hex(bytes);
    // 统一转成 Uint8Array，D1 绑定参数接受 ArrayBuffer / TypedArray
    const buf = await toUint8(bytes);
    await this.db
      .prepare(
        "INSERT INTO files (file_key, bytes, size, sha256, created_at) " +
        "VALUES (?, ?, ?, ?, ?) " +
        "ON CONFLICT(file_key) DO UPDATE SET bytes=excluded.bytes, size=excluded.size, sha256=excluded.sha256"
      )
      .bind(key, buf, size, sha256, new Date().toISOString())
      .run();
    return { provider: "d1", objectKey: key, size, sha256 };
  }

  async get(key) {
    const row = await this.db
      .prepare("SELECT bytes FROM files WHERE file_key = ?")
      .bind(key)
      .first();
    if (!row || row.bytes === null || row.bytes === undefined) {
      return null;
    }
    // D1 读出的 BLOB 可能是 ArrayBuffer/TypedArray，也可能被序列化成普通数组。
    // 统一转成 Uint8Array —— 否则 new Response(body) 会把它当字符串/JSON，
    // 导致下载内容膨胀（本次实测：380KB 的文件下回来变成 1.18MB）。
    return normalizeBytes(row.bytes);
  }

  async list(prefix = "") {
    const result = await this.db
      .prepare("SELECT file_key AS key, size, created_at AS uploaded FROM files WHERE file_key LIKE ?")
      .bind(prefix + "%")
      .all();
    return (result.results || []).map((row) => ({
      key: row.key,
      size: row.size,
      uploaded: row.uploaded,
    }));
  }

  async url(key) {
    return `/download/${encodeURIComponent(key)}`;
  }
}

export function createStorage(env) {
  // 优先用 D1（无 R2 绑定时的可用方案）；将来开通 R2 后改这里的优先顺序即可。
  if (env.DB) {
    return new D1Storage(env.DB);
  }
  if (env.FILES) {
    return new R2Storage(env.FILES);
  }
  throw new Error("缺少存储绑定：需要 D1(DB) 或 R2(FILES)");
}

export async function sha256Hex(bytes) {
  const input = bytes instanceof ArrayBuffer ? bytes : bytes;
  const digest = await crypto.subtle.digest("SHA-256", input);
  return [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

function byteLength(bytes) {
  if (bytes instanceof ArrayBuffer) {
    return bytes.byteLength;
  }
  if (ArrayBuffer.isView(bytes)) {
    return bytes.byteLength;
  }
  return bytes.size || 0;
}

/** 把入参统一成 Uint8Array，供 D1 绑定参数使用。 */
function toUint8(bytes) {
  if (bytes instanceof ArrayBuffer) {
    return new Uint8Array(bytes);
  }
  if (ArrayBuffer.isView(bytes)) {
    return new Uint8Array(bytes.buffer, bytes.byteOffset, bytes.byteLength);
  }
  if (bytes && typeof bytes.arrayBuffer === "function") {
    // Blob / File
    return bytes.arrayBuffer().then((buf) => new Uint8Array(buf));
  }
  throw new Error("不支持的字节类型");
}

/**
 * 把从 D1 读出的 BLOB 统一成 Uint8Array。
 * D1 视驱动/序列化方式不同，可能返回 ArrayBuffer、TypedArray 或普通数字数组；
 * 直接交给 `new Response(body)` 时，后两种会被当成字符串处理导致内容膨胀。
 */
function normalizeBytes(value) {
  if (value instanceof ArrayBuffer) {
    return new Uint8Array(value);
  }
  if (ArrayBuffer.isView(value)) {
    return new Uint8Array(value.buffer, value.byteOffset, value.byteLength);
  }
  if (Array.isArray(value)) {
    return Uint8Array.from(value);
  }
  if (typeof value === "string") {
    // 文本编码
    return new TextEncoder().encode(value);
  }
  if (value && typeof value.arrayBuffer === "function") {
    return value.arrayBuffer().then((buf) => new Uint8Array(buf));
  }
  throw new Error("无法识别的 BLOB 类型：" + Object.prototype.toString.call(value));
}
