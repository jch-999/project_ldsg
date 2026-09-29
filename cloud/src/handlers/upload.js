import { first, run, newId, nowText } from "../db.js";
import { createStorage, sha256Hex } from "../storage.js";
import { ipHmac, preflight } from "../preflight.js";
import { renderMessage, renderUpload, htmlResponse } from "../pages.js";

const MAX_FILE_SIZE = 50 * 1024 * 1024;
const MAX_BODY_SIZE = 52 * 1024 * 1024;

const ALLOWED_EXT = new Set([
  ".pdf", ".docx", ".pptx", ".xlsx", ".zip",
  ".png", ".jpg", ".jpeg", ".md", ".txt", ".epub",
]);

const ALLOWED_CATEGORIES = new Set(["笔记", "真题", "课件", "教材", "其他"]);
const DISPLAY_EXT = ["pdf", "docx", "pptx", "xlsx", "zip", "png", "jpg", "jpeg", "md", "txt", "epub"];

const MIME_BY_EXT = {
  ".pdf": "application/pdf",
  ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ".zip": "application/zip",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".md": "text/markdown; charset=utf-8",
  ".txt": "text/plain; charset=utf-8",
  ".epub": "application/epub+zip",
};

export function handleUploadPage() {
  return htmlResponse(renderUpload());
}

export async function handleUpload(request, env) {
  const contentType = request.headers.get("Content-Type") || "";
  if (!contentType.toLowerCase().startsWith("multipart/form-data")) {
    return htmlResponse(renderUpload("请求格式不对，请从上传页面重新提交。"), 400);
  }

  const contentLength = Number.parseInt(request.headers.get("Content-Length") || "0", 10);
  if (Number.isFinite(contentLength) && contentLength > MAX_BODY_SIZE) {
    return htmlResponse(renderUpload("整个请求超过 52 MB，请选择更小的文件（单个文件上限 50 MB）。"), 413);
  }

  let form;
  try {
    form = await request.formData();
  } catch (error) {
    return htmlResponse(renderUpload(`表单解析失败：${error.message}`), 400);
  }

  const formValues = {
    title: stringField(form, "title"),
    course_code: stringField(form, "course_code"),
    course_name: stringField(form, "course_name"),
    category: stringField(form, "category"),
    semester: stringField(form, "semester"),
    tags: stringField(form, "tags"),
    description: stringField(form, "description"),
    uploader_note: stringField(form, "uploader_note"),
  };

  const file = form.get("file");
  if (!file || typeof file === "string") {
    return htmlResponse(renderUpload("你没有选择文件，请重新选择。", formValues), 400);
  }

  const originalName = baseName(file.name || "");
  const title = formValues.title.trim();

  if (!title) {
    return htmlResponse(renderUpload("标题不能为空。", formValues), 400);
  }

  const ext = extensionOf(originalName);
  if (!ALLOWED_EXT.has(ext)) {
    return htmlResponse(renderUpload(
      `不支持的文件类型：${ext || "（无扩展名）"}。允许的类型是 ${DISPLAY_EXT.map((item) => `.${item}`).join(" / ")}。`,
      formValues,
    ), 400);
  }

  if (!file.size) {
    return htmlResponse(renderUpload("文件是空的，请重新选择。", formValues), 400);
  }
  if (file.size > MAX_FILE_SIZE) {
    return htmlResponse(renderUpload(
      `文件太大：${(file.size / 1024 / 1024).toFixed(1)} MB，上限 50 MB。`,
      formValues,
    ), 413);
  }

  const rawBytes = new Uint8Array(await file.arrayBuffer());
  if (rawBytes.byteLength === 0) {
    return htmlResponse(renderUpload("文件是空的，请重新选择。", formValues), 400);
  }
  if (rawBytes.byteLength > MAX_FILE_SIZE) {
    return htmlResponse(renderUpload(
      `文件太大：${(rawBytes.byteLength / 1024 / 1024).toFixed(1)} MB，上限 50 MB。`,
      formValues,
    ), 413);
  }

  let bytes;
  let metadataNote;
  try {
    const stripped = await stripMetadata(originalName, rawBytes);
    bytes = stripped.bytes;
    metadataNote = stripped.note;
  } catch (error) {
    return htmlResponse(renderUpload(
      `清除文件元数据时出错，为避免泄露隐私，本次上传没有保存。原因：${error.message}`,
      formValues,
    ), 500);
  }

  const category = ALLOWED_CATEGORIES.has(formValues.category.trim()) ? formValues.category.trim() : "其他";
  const tags = splitTags(formValues.tags);
  const tagsJson = tags.length ? JSON.stringify(tags) : null;
  const sha256Value = await sha256Hex(bytes);
  const verdict = preflight({
    filename: originalName,
    mime: file.type || MIME_BY_EXT[ext] || "application/octet-stream",
    size: bytes.byteLength,
    bytes,
    title,
    description: formValues.description,
    courseCode: formValues.course_code,
  });
  const ipValue = await ipHmac(request, env);
  const createdAt = nowText();

  if (verdict.decision === "reject") {
    await run(
      env.DB,
      "INSERT INTO intercept_log " +
      "(id, action, rule, filename, course_code, byte_size, sha256, ip_hmac, credential, created_at) " +
      "VALUES (?,?,?,?,?,?,?,?,?,?)",
      [
        newId(),
        "rejected",
        verdict.rule,
        originalName,
        formValues.course_code,
        bytes.byteLength,
        sha256Value,
        ipValue,
        null,
        createdAt,
      ],
    );
    return htmlResponse(renderMessage(
      "上传被拒绝",
      `系统预检命中规则：${verdict.rule}。该文件没有写入对象存储，也没有进入审核队列。`,
      [["/", "回到首页"], ["/upload", "重新上传"]],
    ), 403);
  }

  const existed = await first(
    env.DB,
    "SELECT id, title, status FROM materials WHERE sha256 = ? ORDER BY created_at DESC LIMIT 1",
    [sha256Value],
  );
  if (existed) {
    return htmlResponse(renderUpload(null, formValues, existed));
  }

  const materialId = newId();
  const fileKey = `uploads/${sha256Value.slice(0, 16)}_${materialId.slice(0, 8)}${ext}`;
  const fileName = buildCanonicalName(formValues.course_code, category, formValues.semester, materialId, ext);
  const mimeType = file.type || MIME_BY_EXT[ext] || "application/octet-stream";
  const interceptFlag = verdict.decision === "flag" ? verdict.rule : null;
  const storage = createStorage(env);
  const stored = await storage.put(fileKey, bytes, {
    httpMetadata: { contentType: mimeType },
    customMetadata: { material_id: materialId },
  });

  await run(
    env.DB,
    "INSERT INTO materials (" +
    "id, title, description, course_code, course_name, category, semester, tags," +
    "file_key, file_name, original_name, file_size, mime_type, sha256," +
    "uploader_note, upload_credential, status, downloads, views, ip_hmac, intercept_flag, created_at, updated_at" +
    ") VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
    [
      materialId,
      title,
      formValues.description,
      formValues.course_code,
      formValues.course_name,
      category,
      formValues.semester,
      tagsJson,
      fileKey,
      fileName,
      originalName,
      stored.size,
      mimeType,
      stored.sha256,
      formValues.uploader_note,
      null,
      "pending",
      0,
      0,
      ipValue,
      interceptFlag,
      createdAt,
      createdAt,
    ],
  );
  await run(
    env.DB,
    "INSERT INTO material_sources (material_id, provider, object_key, size, sha256, priority) VALUES (?,?,?,?,?,?)",
    [materialId, stored.provider, stored.objectKey, stored.size, stored.sha256, 0],
  );
  await run(
    env.DB,
    "INSERT INTO audit_log (id, material_id, action, reason, actor, created_at) VALUES (?,?,?,?,?,?)",
    [newId(), materialId, "upload", "用户上传，等待审核", "uploader", createdAt],
  );

  if (interceptFlag) {
    await run(
      env.DB,
      "INSERT INTO intercept_log " +
      "(id, action, rule, filename, course_code, byte_size, sha256, ip_hmac, credential, created_at) " +
      "VALUES (?,?,?,?,?,?,?,?,?,?)",
      [
        newId(),
        "flagged",
        interceptFlag,
        originalName,
        formValues.course_code,
        stored.size,
        stored.sha256,
        ipValue,
        null,
        createdAt,
      ],
    );
  }

  return htmlResponse(renderMessage(
    "上传成功，等待审核",
    `《${title}》已保存。管理员审核通过后，它才会出现在首页。系统已执行元数据清除：${metadataNote}`,
    [["/", "回到首页"], ["/upload", "再传一份"]],
  ));
}

function stringField(form, name) {
  const value = form.get(name);
  return typeof value === "string" ? value.trim() : "";
}

function baseName(name) {
  const normalized = String(name || "").replace(/\\/g, "/");
  return normalized.split("/").pop() || "";
}

function extensionOf(filename) {
  const dot = String(filename || "").lastIndexOf(".");
  return dot >= 0 ? String(filename).slice(dot).toLowerCase() : "";
}

function splitTags(raw) {
  return String(raw || "")
    .split(/[,，;；、]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function buildCanonicalName(courseCode, category, semester, materialId, ext) {
  let stem = [courseCode, category, semester]
    .map((value) => String(value || "").trim())
    .filter(Boolean)
    .join("_");
  stem = stem.replace(/[^\w\u4e00-\u9fff-]+/gu, "_").replace(/^_+|_+$/g, "");
  if (!stem) {
    stem = "material";
  }
  return `${stem}_${materialId.slice(0, 8)}${ext}`;
}

async function stripMetadata(filename, input) {
  const ext = extensionOf(filename);
  if (ext === ".jpg" || ext === ".jpeg") {
    return stripJpeg(input);
  }
  if (ext === ".png") {
    return stripPng(input);
  }
  if (ext === ".pdf") {
    return stripPdf(input);
  }
  if (ext === ".docx" || ext === ".pptx" || ext === ".xlsx") {
    return stripOoxml(input);
  }
  return {
    bytes: input,
    note: "该格式本期不处理元数据，已原样保存。",
  };
}

function stripJpeg(input) {
  if (input[0] !== 0xff || input[1] !== 0xd8) {
    throw new Error("不是合法的 JPEG 文件（缺少 FFD8 起始标记）");
  }

  const chunks = [new Uint8Array([0xff, 0xd8])];
  const removed = [];
  let pos = 2;

  while (pos < input.length) {
    if (input[pos] !== 0xff) {
      chunks.push(input.slice(pos));
      break;
    }

    const start = pos;
    while (pos < input.length && input[pos] === 0xff) {
      pos += 1;
    }
    if (pos >= input.length) {
      break;
    }
    const marker = input[pos];
    pos += 1;

    if (marker === 0xd9) {
      chunks.push(input.slice(start, pos));
      break;
    }
    if (marker === 0xda) {
      chunks.push(input.slice(start));
      break;
    }
    if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) {
      chunks.push(input.slice(start, pos));
      continue;
    }
    if (pos + 2 > input.length) {
      chunks.push(input.slice(start));
      break;
    }

    const length = (input[pos] << 8) | input[pos + 1];
    const end = pos + length;
    if (end > input.length) {
      throw new Error("JPEG 段长度越界");
    }
    const payloadStart = pos + 2;

    if (marker === 0xe1 && startsWith(input, payloadStart, [0x45, 0x78, 0x69, 0x66, 0x00, 0x00])) {
      removed.push("JPEG EXIF (APP1)");
    } else if (marker === 0xe1) {
      removed.push("JPEG XMP (APP1)");
    } else if (marker === 0xed) {
      removed.push("JPEG IPTC/Photoshop (APP13)");
    } else if (marker === 0xfe) {
      removed.push("JPEG 注释 (COM)");
    } else {
      chunks.push(input.slice(start, end));
    }
    pos = end;
  }

  return {
    bytes: concat(chunks),
    note: "已删除 JPEG 的 EXIF / XMP / IPTC / 注释段。",
    removed,
  };
}

function stripPng(input) {
  if (!startsWith(input, 0, [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a])) {
    throw new Error("不是合法的 PNG 文件（签名不对）");
  }

  const dropTypes = new Set(["tEXt", "zTXt", "iTXt", "eXIf", "tIME"]);
  const labels = {
    tEXt: "PNG tEXt 文本块",
    zTXt: "PNG zTXt 压缩文本块",
    iTXt: "PNG iTXt 国际文本块",
    eXIf: "PNG eXIf EXIF块",
    tIME: "PNG tIME 时间戳块",
  };
  const chunks = [input.slice(0, 8)];
  const removed = [];
  let pos = 8;

  while (pos + 8 <= input.length) {
    const length = readU32(input, pos);
    const type = ascii(input, pos + 4, 4);
    const total = 12 + length;
    if (pos + total > input.length) {
      throw new Error("PNG 块长度越界");
    }
    if (dropTypes.has(type)) {
      removed.push(labels[type] || type);
    } else {
      chunks.push(input.slice(pos, pos + total));
    }
    pos += total;
    if (type === "IEND") {
      break;
    }
  }

  return {
    bytes: concat(chunks),
    note: "已删除 PNG 的文本 / EXIF / 时间戳块。",
    removed,
  };
}

const PDF_INFO_KEYS = [
  "Author", "Creator", "Producer", "Title", "Subject",
  "Keywords", "CreationDate", "ModDate", "Company",
  "Manager", "LastModifiedBy",
];

function stripPdf(input) {
  let text = latin1FromBytes(input);
  let changed = false;

  for (const key of PDF_INFO_KEYS) {
    const literal = new RegExp(`/${key}\\s*\\(([^)]*)\\)`, "g");
    text = text.replace(literal, (match, body) => {
      if (!body.trim()) {
        return match;
      }
      changed = true;
      return match.slice(0, match.length - body.length) + " ".repeat(body.length);
    });

    const hex = new RegExp(`/${key}\\s*<([0-9A-Fa-f\\s]*)>`, "g");
    text = text.replace(hex, (match, body) => {
      if (!body.trim()) {
        return match;
      }
      changed = true;
      return match.slice(0, match.length - body.length) + " ".repeat(body.length);
    });
  }

  const bytes = latin1ToBytes(text);
  let strippedXmp = false;
  for (let index = 0; index + 7 < bytes.length; index += 1) {
    const hasStream =
      matchesAscii(bytes, index, "stream\n") ||
      matchesAscii(bytes, index, "stream\r\n");
    if (!hasStream) {
      continue;
    }
    const contentStart = matchesAscii(bytes, index, "stream\r\n") ? index + 8 : index + 7;
    const endIndex = indexOfAscii(bytes, "endstream", contentStart);
    if (endIndex < 0) {
      continue;
    }
    const content = latin1FromBytes(bytes.slice(contentStart, endIndex)).toLowerCase();
    if (content.includes("xmpmeta") || content.includes("xpacket") || content.includes("adobe:ns:meta")) {
      for (let cursor = contentStart; cursor < endIndex; cursor += 1) {
        if (bytes[cursor] !== 0x0a && bytes[cursor] !== 0x0d) {
          bytes[cursor] = 0x20;
        }
      }
      strippedXmp = true;
    }
  }

  let note = "已尽力清除 PDF 的 /Info 与 XMP 元数据。";
  if (!changed && !strippedXmp) {
    note += "（未找到明文元数据，可能被压缩在对象流里，当前方案无法处理。）";
  } else if (!changed) {
    note += "（未发现明文 /Info 字典，可能被压缩。）";
  }
  return { bytes, note };
}

async function stripOoxml(input) {
  const entries = readZipEntries(input);
  const rewritten = [];

  for (const entry of entries) {
    let data;
    if (entry.method === 0) {
      data = entry.rawData;
    } else if (entry.method === 8) {
      data = await inflateRaw(entry.rawData);
    } else {
      throw new Error(`不支持的 ZIP 压缩方法：${entry.method}`);
    }

    if (entry.name === "docProps/core.xml") {
      data = cleanCoreXml(data);
    } else if (entry.name === "docProps/app.xml") {
      data = cleanAppXml(data);
    } else if (entry.name === "docProps/custom.xml") {
      data = cleanCustomXml(data);
    }
    rewritten.push({ name: entry.name, data });
  }

  return {
    bytes: await buildZip(rewritten),
    note: "已清理 docProps 下的作者 / 公司 / 修订等属性。",
  };
}

function cleanCoreXml(input) {
  let text = new TextDecoder().decode(input);
  const blankTags = [
    "dc:creator", "cp:lastModifiedBy", "dc:subject",
    "cp:keywords", "cp:category", "cp:lastPrinted",
  ];
  for (const tag of blankTags) {
    text = replaceTagText(text, tag, "");
  }
  text = replaceTagText(text, "cp:revision", "1");
  text = replaceTagText(text, "dcterms:created", "2000-01-01T00:00:00Z");
  text = replaceTagText(text, "dcterms:modified", "2000-01-01T00:00:00Z");
  return new TextEncoder().encode(text);
}

function cleanAppXml(input) {
  let text = new TextDecoder().decode(input);
  for (const tag of ["Company", "Manager", "Template", "TotalTime", "AppVersion", "HyperlinkBase"]) {
    text = replaceTagText(text, tag, "");
  }
  text = replaceTagText(text, "Application", "Local");
  return new TextEncoder().encode(text);
}

function cleanCustomXml(input) {
  const text = new TextDecoder().decode(input);
  return new TextEncoder().encode(
    text.replace(/(<Properties\b[^>]*>)[\s\S]*?(<\/Properties>)/, "$1$2"),
  );
}

function replaceTagText(text, tag, value) {
  const safeTag = tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const pattern = new RegExp(`(<${safeTag}\\b[^>]*>)[\\s\\S]*?(</${safeTag}>)`, "g");
  return text.replace(pattern, `$1${value}$2`);
}

function readZipEntries(input) {
  const eocd = findEocd(input);
  if (eocd < 0) {
    throw new Error("不是合法的 ZIP/OOXML 文件（找不到 EOCD）");
  }
  const totalEntries = readU16(input, eocd + 10);
  let offset = readU32(input, eocd + 16);
  const entries = [];

  for (let index = 0; index < totalEntries; index += 1) {
    if (readU32(input, offset) !== 0x02014b50) {
      throw new Error("ZIP 中央目录损坏");
    }
    const method = readU16(input, offset + 10);
    const compressedSize = readU32(input, offset + 20);
    const uncompressedSize = readU32(input, offset + 24);
    const nameLength = readU16(input, offset + 28);
    const extraLength = readU16(input, offset + 30);
    const commentLength = readU16(input, offset + 32);
    const localOffset = readU32(input, offset + 42);
    const name = new TextDecoder().decode(input.slice(offset + 46, offset + 46 + nameLength));

    if (compressedSize === 0xffffffff || uncompressedSize === 0xffffffff || localOffset === 0xffffffff) {
      throw new Error("暂不支持 ZIP64 的 OOXML 文件");
    }

    if (readU32(input, localOffset) !== 0x04034b50) {
      throw new Error("ZIP 本地文件头损坏");
    }
    const localNameLength = readU16(input, localOffset + 26);
    const localExtraLength = readU16(input, localOffset + 28);
    const dataStart = localOffset + 30 + localNameLength + localExtraLength;
    const rawData = input.slice(dataStart, dataStart + compressedSize);

    entries.push({ name, method, rawData });
    offset += 46 + nameLength + extraLength + commentLength;
  }

  return entries;
}

function findEocd(input) {
  const min = Math.max(0, input.length - 0xffff - 22);
  for (let index = input.length - 22; index >= min; index -= 1) {
    if (readU32(input, index) === 0x06054b50) {
      return index;
    }
  }
  return -1;
}

async function buildZip(entries) {
  const localParts = [];
  const centralParts = [];
  let offset = 0;
  const nowDate = 0x0021;
  const nowTime = 0;

  for (const entry of entries) {
    const nameBytes = new TextEncoder().encode(entry.name);
    const crc = crc32(entry.data);
    const compressed = await deflateRaw(entry.data);
    const useStored = compressed.length >= entry.data.length;
    const method = useStored ? 0 : 8;
    const payload = useStored ? entry.data : compressed;

    const local = new Uint8Array(30 + nameBytes.length + payload.length);
    let cursor = 0;
    cursor = writeU32(local, cursor, 0x04034b50);
    cursor = writeU16(local, cursor, 20);
    cursor = writeU16(local, cursor, 0x0800);
    cursor = writeU16(local, cursor, method);
    cursor = writeU16(local, cursor, nowTime);
    cursor = writeU16(local, cursor, nowDate);
    cursor = writeU32(local, cursor, crc);
    cursor = writeU32(local, cursor, payload.length);
    cursor = writeU32(local, cursor, entry.data.length);
    cursor = writeU16(local, cursor, nameBytes.length);
    cursor = writeU16(local, cursor, 0);
    local.set(nameBytes, cursor);
    cursor += nameBytes.length;
    local.set(payload, cursor);
    localParts.push(local);

    const central = new Uint8Array(46 + nameBytes.length);
    cursor = 0;
    cursor = writeU32(central, cursor, 0x02014b50);
    cursor = writeU16(central, cursor, 20);
    cursor = writeU16(central, cursor, 20);
    cursor = writeU16(central, cursor, 0x0800);
    cursor = writeU16(central, cursor, method);
    cursor = writeU16(central, cursor, nowTime);
    cursor = writeU16(central, cursor, nowDate);
    cursor = writeU32(central, cursor, crc);
    cursor = writeU32(central, cursor, payload.length);
    cursor = writeU32(central, cursor, entry.data.length);
    cursor = writeU16(central, cursor, nameBytes.length);
    cursor = writeU16(central, cursor, 0);
    cursor = writeU16(central, cursor, 0);
    cursor = writeU16(central, cursor, 0);
    cursor = writeU16(central, cursor, 0);
    cursor = writeU32(central, cursor, 0);
    cursor = writeU32(central, cursor, offset);
    central.set(nameBytes, cursor);
    centralParts.push(central);

    offset += local.length;
  }

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const eocd = new Uint8Array(22);
  let cursor = 0;
  cursor = writeU32(eocd, cursor, 0x06054b50);
  cursor = writeU16(eocd, cursor, 0);
  cursor = writeU16(eocd, cursor, 0);
  cursor = writeU16(eocd, cursor, entries.length);
  cursor = writeU16(eocd, cursor, entries.length);
  cursor = writeU32(eocd, cursor, centralSize);
  cursor = writeU32(eocd, cursor, offset);
  writeU16(eocd, cursor, 0);

  return concat([...localParts, ...centralParts, eocd]);
}

async function inflateRaw(data) {
  const stream = new Blob([data]).stream().pipeThrough(new DecompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

async function deflateRaw(data) {
  const stream = new Blob([data]).stream().pipeThrough(new CompressionStream("deflate-raw"));
  return new Uint8Array(await new Response(stream).arrayBuffer());
}

let crcTable = null;

function crc32(bytes) {
  if (!crcTable) {
    crcTable = new Uint32Array(256);
    for (let index = 0; index < 256; index += 1) {
      let value = index;
      for (let bit = 0; bit < 8; bit += 1) {
        value = (value & 1) ? (0xedb88320 ^ (value >>> 1)) : (value >>> 1);
      }
      crcTable[index] = value >>> 0;
    }
  }
  let crc = 0xffffffff;
  for (const byte of bytes) {
    crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function startsWith(input, offset, bytes) {
  if (offset + bytes.length > input.length) {
    return false;
  }
  for (let index = 0; index < bytes.length; index += 1) {
    if (input[offset + index] !== bytes[index]) {
      return false;
    }
  }
  return true;
}

function ascii(input, offset, length) {
  return String.fromCharCode(...input.slice(offset, offset + length));
}

function matchesAscii(input, offset, text) {
  return startsWith(input, offset, [...text].map((char) => char.charCodeAt(0)));
}

function indexOfAscii(input, text, start) {
  const needle = [...text].map((char) => char.charCodeAt(0));
  for (let index = start; index <= input.length - needle.length; index += 1) {
    if (startsWith(input, index, needle)) {
      return index;
    }
  }
  return -1;
}

function latin1FromBytes(bytes) {
  let result = "";
  for (let index = 0; index < bytes.length; index += 0x8000) {
    result += String.fromCharCode(...bytes.subarray(index, index + 0x8000));
  }
  return result;
}

function latin1ToBytes(text) {
  const bytes = new Uint8Array(text.length);
  for (let index = 0; index < text.length; index += 1) {
    bytes[index] = text.charCodeAt(index) & 0xff;
  }
  return bytes;
}

function readU16(input, offset) {
  return input[offset] | (input[offset + 1] << 8);
}

function readU32(input, offset) {
  return (
    (input[offset] |
      (input[offset + 1] << 8) |
      (input[offset + 2] << 16) |
      (input[offset + 3] << 24)) >>> 0
  );
}

function writeU16(target, offset, value) {
  target[offset] = value & 0xff;
  target[offset + 1] = (value >>> 8) & 0xff;
  return offset + 2;
}

function writeU32(target, offset, value) {
  target[offset] = value & 0xff;
  target[offset + 1] = (value >>> 8) & 0xff;
  target[offset + 2] = (value >>> 16) & 0xff;
  target[offset + 3] = (value >>> 24) & 0xff;
  return offset + 4;
}

function concat(chunks) {
  const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
  const output = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    output.set(chunk, offset);
    offset += chunk.length;
  }
  return output;
}
