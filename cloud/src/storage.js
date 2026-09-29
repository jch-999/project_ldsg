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
export function createStorage(env) {
  if (!env.FILES) {
    throw new Error("缺少 R2 绑定 FILES");
  }
  return new R2Storage(env.FILES);
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
