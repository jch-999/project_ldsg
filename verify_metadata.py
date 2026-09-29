"""
元数据剥离功能 · 手工验证脚本
============================

这个脚本不是测试框架（没有 pytest），只是把「手工验证」变成一条可以反复执行的命令：

    python verify_metadata.py

它会：
    1. 在 selftest_tmp/ 里生成 4 个带元数据的样例文件；
    2. 调用 metadata.strip_metadata() 清理它们；
    3. 打开清理后的文件，检查那些元数据是不是真的没了；
    4. 打印每一行的 PASS / FAIL。

它验证的是「独立函数」这条要求：metadata.strip_metadata() 完全可以脱离
上传流程，单独拿文件来跑。
"""

import base64
import os
import shutil
import sys
import zipfile
import zlib

import metadata


TMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "selftest_tmp")

# 一张 1x1 的合法 PNG
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

# 一张 1x1 的合法 JPEG
JPEG_1X1 = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AKp//2Q=="
)


# ---------------------------------------------------------------------------
# 造样例文件
# ---------------------------------------------------------------------------

def make_docx(path):
    """造一个带作者/公司/自定义属性的最小 docx。"""
    content_types = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        b'<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        b'<Default Extension="xml" ContentType="application/xml"/>'
        b'<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        b'<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        b'<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        b'<Override PartName="/docProps/custom.xml" ContentType="application/vnd.openxmlformats-officedocument.custom-properties+xml"/>'
        b'</Types>'
    )
    rels = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        b'<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
        b'<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
        b'<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
        b'</Relationships>'
    )
    document = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        b'<w:body><w:p><w:r><w:t>Hello</w:t></w:r></w:p></w:body></w:document>'
    )
    core = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<cp:coreProperties '
        b'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        b'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        b'xmlns:dcterms="http://purl.org/dc/terms/" '
        b'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        b'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        b'<dc:creator>Alice Author</dc:creator>'
        b'<cp:lastModifiedBy>Bob Editor</cp:lastModifiedBy>'
        b'<cp:revision>42</cp:revision>'
        b'<dcterms:created xsi:type="dcterms:W3CDTF">2026-01-02T03:04:05Z</dcterms:created>'
        b'<dcterms:modified xsi:type="dcterms:W3CDTF">2026-06-07T08:09:10Z</dcterms:modified>'
        b'<cp:keywords>secret-keywords</cp:keywords>'
        b'</cp:coreProperties>'
    )
    app = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        b'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        b'<Application>Microsoft Office Word</Application>'
        b'<Company>ACME Corporation</Company>'
        b'<Manager>Carol Boss</Manager>'
        b'<TotalTime>987</TotalTime>'
        b'<AppVersion>16.0000</AppVersion>'
        b'</Properties>'
    )
    custom = (
        b'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        b'<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/custom-properties" '
        b'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        b'<property fmtid="{D5CDD505-2E9C-101B-9397-08002B2CF9AE}" pid="2" name="MyPrivateField">'
        b'<vt:lpwstr>my secret value</vt:lpwstr></property></Properties>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", document)
        z.writestr("docProps/core.xml", core)
        z.writestr("docProps/app.xml", app)
        z.writestr("docProps/custom.xml", custom)


def make_png(path):
    """在合法 PNG 里塞进 tEXt / tIME / eXIf 元数据块。"""
    def chunk(chunk_type, payload):
        crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
        return len(payload).to_bytes(4, "big") + chunk_type + payload + crc.to_bytes(4, "big")

    signature = PNG_1X1[:8]
    pos = 8
    ihdr = b""
    rest = b""
    while pos < len(PNG_1X1):
        length = int.from_bytes(PNG_1X1[pos:pos + 4], "big")
        ctype = PNG_1X1[pos + 4:pos + 8]
        total = 12 + length
        piece = PNG_1X1[pos:pos + total]
        if ctype == b"IHDR":
            ihdr = piece
        elif ctype != b"IEND":
            rest += piece
        pos += total

    with open(path, "wb") as f:
        f.write(signature)
        f.write(ihdr)
        f.write(chunk(b"tEXt", b"Author\x00Alice Author"))
        f.write(chunk(b"tIME", b"\x07\xe8\x06\x07\x08\x09\x0a"))
        f.write(chunk(b"eXIf", b"Exif\x00\x00fake-exif-payload"))
        f.write(rest)
        f.write(chunk(b"IEND", b""))


def make_jpeg(path):
    """在合法 JPEG 的 SOI 之后插入一个带 EXIF 的 APP1 段。"""
    payload = b"Exif\x00\x00" + b"MM\x00\x2a" + b"\x00\x08" + b"fake-exif-body"
    segment_length = len(payload) + 2
    app1 = b"\xff\xe1" + segment_length.to_bytes(2, "big") + payload
    with open(path, "wb") as f:
        f.write(JPEG_1X1[:2] + app1 + JPEG_1X1[2:])


def make_pdf(path):
    """造一个结构正确、xref 偏移正确的 PDF，带 /Info 和 XMP。"""
    objects = {}
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>"
    objects[3] = b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Contents 4 0 R /Resources << >> >>"
    content = b"0 0 m 200 200 l S\n"
    objects[4] = b"<< /Length %d >>\nstream\n" % len(content) + content + b"endstream"
    objects[5] = (
        b"<< /Author (Zhang San) /Creator (TestTool 1.0) /Producer (SecretProducer) "
        b"/Title (My Private Notes) /CreationDate (D:20260101120000+08'00') >>"
    )
    xmp = (
        b'<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        b'<dc:creator><rdf:Seq><rdf:li>Zhang San</rdf:li></rdf:Seq></dc:creator>'
        b'</rdf:Description></rdf:RDF></x:xmpmeta>\n'
        b'<?xpacket end="w"?>'
    )
    objects[6] = b"<< /Type /Metadata /Subtype /XML /Length %d >>\nstream\n" % len(xmp) + xmp + b"\nendstream"

    buf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = {}
    for number in sorted(objects):
        offsets[number] = len(buf)
        buf += ("%d 0 obj\n" % number).encode("ascii") + objects[number] + b"\nendobj\n"
    xref_pos = len(buf)
    buf += b"xref\n0 7\n0000000000 65535 f \n"
    for number in range(1, 7):
        buf += ("%010d 00000 n \n" % offsets[number]).encode("ascii")
    buf += b"trailer\n<< /Size 7 /Root 1 0 R /Info 5 0 R >>\nstartxref\n%d\n%%%%EOF\n" % xref_pos
    with open(path, "wb") as f:
        f.write(bytes(buf))


# ---------------------------------------------------------------------------
# 检查清理后的文件
# ---------------------------------------------------------------------------

RESULTS = []


def check(name, ok, detail):
    RESULTS.append((name, ok, detail))
    print("[%s] %-46s %s" % ("PASS" if ok else "FAIL", name, detail))


def verify_docx(path):
    with zipfile.ZipFile(path) as z:
        core = z.read("docProps/core.xml").decode("utf-8")
        app = z.read("docProps/app.xml").decode("utf-8")
        custom = z.read("docProps/custom.xml").decode("utf-8")
    for token in ("Alice Author", "Bob Editor", "secret-keywords", "2026-01-02T03:04:05Z"):
        check("docx 不再包含 %r" % token, token not in core, "core.xml")
    for token in ("ACME Corporation", "Carol Boss", "987", "16.0000"):
        check("docx 不再包含 %r" % token, token not in app, "app.xml")
    check("docx 自定义属性被清空", "my secret value" not in custom and "<property" not in custom, "custom.xml")
    check("docx 修订号被改成中性值 1", "<cp:revision>1</cp:revision>" in core, "core.xml")
    check("docx 仍是可打开的 zip", zipfile.is_zipfile(path), "zip 完整性")


def verify_png(path):
    with open(path, "rb") as f:
        data = f.read()
    check("png 文件签名正确", data[:8] == b"\x89PNG\r\n\x1a\n", "PNG signature")
    types = []
    pos = 8
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        types.append(data[pos + 4:pos + 8])
        pos += 12 + length
        if types[-1] == b"IEND":
            break
    check("png 元数据块已删除", not ({b"tEXt", b"tIME", b"eXIf"} & set(types)), "chunks=%s" % [t.decode() for t in types])
    check("png 图像块仍完整", b"IHDR" in types and b"IDAT" in types and b"IEND" in types, "IHDR/IDAT/IEND 都在")


def verify_jpeg(path):
    with open(path, "rb") as f:
        data = f.read()
    check("jpg 起始/结束标记正确", data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9", "SOI/EOI")
    markers = []
    pos = 2
    while pos < len(data) - 1:
        if data[pos] != 0xFF:
            break
        marker = data[pos + 1]
        markers.append(marker)
        if marker in (0xD9,):
            break
        if marker == 0xDA:
            break
        seg_len = int.from_bytes(data[pos + 2:pos + 4], "big")
        pos += 2 + seg_len
    check("jpg 的 EXIF/APP1 段已删除", 0xE1 not in markers, "markers=%s" % [hex(m) for m in markers])
    check("jpg 其他段保留", 0xDB in markers or 0xC0 in markers, "包含量化表或帧头")


def verify_pdf(src_path, dst_path):
    with open(src_path, "rb") as f:
        src = f.read()
    with open(dst_path, "rb") as f:
        dst = f.read()
    check("pdf 长度不变（xref 偏移不失效）", len(src) == len(dst), "%d -> %d 字节" % (len(src), len(dst)))
    check("pdf 文件头尾完整", dst.startswith(b"%PDF") and dst.rstrip().endswith(b"%%EOF"), "header/trailer")
    for token in (b"Zhang San", b"SecretProducer", b"My Private Notes", b"TestTool 1.0"):
        check("pdf 不再包含 %r" % token.decode(), token not in dst, "/Info 字符串")
    check("pdf XMP 元数据已被清空", b"xmpmeta" not in dst, "XMP 流")


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def main():
    if os.path.isdir(TMP_DIR):
        shutil.rmtree(TMP_DIR)
    os.makedirs(TMP_DIR)

    cases = [
        ("document.docx", make_docx, "document_clean.docx", verify_docx),
        ("image.png", make_png, "image_clean.png", verify_png),
        ("photo.jpg", make_jpeg, "photo_clean.jpg", verify_jpeg),
        ("report.pdf", make_pdf, "report_clean.pdf", None),
    ]

    generated = {}
    for src_name, maker, dst_name, verifier in cases:
        src = os.path.join(TMP_DIR, src_name)
        dst = os.path.join(TMP_DIR, dst_name)
        maker(src)
        generated[src_name] = (src, dst)
        print("\n--- metadata.strip_metadata(%s, %s) ---" % (src_name, dst_name))
        result = metadata.strip_metadata(src, dst)
        print("返回: kind=%s stripped=%s removed=%s" % (result["kind"], result["stripped"], result["removed"]))
        print("说明: %s" % result["note"])

    print("\n=== 检查清理结果 ===")
    verify_docx(os.path.join(TMP_DIR, "document_clean.docx"))
    verify_png(os.path.join(TMP_DIR, "image_clean.png"))
    verify_jpeg(os.path.join(TMP_DIR, "photo_clean.jpg"))
    src, dst = generated["report.pdf"]
    verify_pdf(src, dst)

    # 顺带验证：不支持的扩展名会原样复制
    plain_src = os.path.join(TMP_DIR, "note.md")
    plain_dst = os.path.join(TMP_DIR, "note_clean.md")
    with open(plain_src, "w", encoding="utf-8") as f:
        f.write("# hello\n")
    result = metadata.strip_metadata(plain_src, plain_dst)
    same = open(plain_src, "rb").read() == open(plain_dst, "rb").read()
    print("\n--- metadata.strip_metadata(note.md, note_clean.md) ---")
    print("返回: kind=%s stripped=%s note=%s" % (result["kind"], result["stripped"], result["note"]))
    check("md 原样复制", same and result["kind"] == "passthrough", "passthrough")

    failed = [row for row in RESULTS if not row[1]]
    print("\n总计 %d 项，通过 %d 项，失败 %d 项。" % (len(RESULTS), len(RESULTS) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
