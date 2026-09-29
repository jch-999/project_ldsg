"""
元数据剥离模块
================

本文件把「清除文件里的隐私元数据」这件事单独做成一个函数，
和上传流程完全解耦。你可以这样单独调用它来验证效果：

    python metadata.py 输入文件.pdf 输出文件.pdf

也可以在别的 Python 代码里调用：

    import metadata
    result = metadata.strip_metadata("输入.docx", "输出.docx")
    print(result)

支持的类型：
    - PDF（尽力而为，见文件末尾说明）
    - Office 文档：.docx / .pptx / .xlsx
    - 图片：.jpg / .jpeg / .png
    - .md / .txt / .zip / .epub：原样复制（这些格式要么没有元数据，要么本期不处理）

全部只用 Python 标准库，不需要 pip install 任何东西。
"""

import json
import os
import re
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET


# ---------------------------------------------------------------------------
# 一、格式分类与统一入口
# ---------------------------------------------------------------------------

PDF_EXT = {".pdf"}
OOXML_EXT = {".docx", ".pptx", ".xlsx"}          # Office 的 zip+xml 格式
JPEG_EXT = {".jpg", ".jpeg"}
PNG_EXT = {".png"}
PASSTHROUGH_EXT = {".md", ".txt", ".zip", ".epub"}


def strip_metadata(src_path, dst_path):
    """
    读取 src_path 指向的文件，去除其中的元数据，写到 dst_path。

    参数：
        src_path：输入文件的路径
        dst_path：输出文件的路径（会被覆盖）

    返回：
        一个 dict，描述做了什么。例如：
        {
          "src": "...",
          "dst": "...",
          "kind": "ooxml",
          "stripped": True,
          "removed": ["creator", "Company", "revision"],
          "note": ""
        }

    注意：这个函数只负责处理文件，不关心数据库、不关心上传，
    所以可以单独拿一个文件来反复测试。
    """
    src_path = os.path.abspath(src_path)
    dst_path = os.path.abspath(dst_path)

    if not os.path.isfile(src_path):
        raise FileNotFoundError("找不到输入文件：%s" % src_path)

    ext = os.path.splitext(src_path)[1].lower()
    removed = []

    if ext in PDF_EXT:
        kind = "pdf"
        note = _strip_pdf(src_path, dst_path, removed)
        stripped = True
    elif ext in OOXML_EXT:
        kind = "ooxml"
        note = _strip_ooxml(src_path, dst_path, removed)
        stripped = True
    elif ext in JPEG_EXT:
        kind = "jpeg"
        note = _strip_jpeg(src_path, dst_path, removed)
        stripped = True
    elif ext in PNG_EXT:
        kind = "png"
        note = _strip_png(src_path, dst_path, removed)
        stripped = True
    elif ext in PASSTHROUGH_EXT:
        kind = "passthrough"
        shutil.copyfile(src_path, dst_path)
        note = "该格式本期不处理元数据，已原样复制。"
        stripped = False
    else:
        # 未知格式也原样复制，避免上传流程因为元数据模块而崩溃。
        kind = "passthrough"
        shutil.copyfile(src_path, dst_path)
        note = "不认识的扩展名 %s，已原样复制。" % (ext or "(无)")
        stripped = False

    return {
        "src": src_path,
        "dst": dst_path,
        "kind": kind,
        "stripped": stripped,
        "removed": removed,
        "note": note,
    }


# ---------------------------------------------------------------------------
# 二、Office 文档（docx / pptx / xlsx）
# ---------------------------------------------------------------------------
#
# 这些文件本质上是一个 zip 包，里面有几个 XML 保存着作者、公司、修订信息：
#   docProps/core.xml   -> 作者、最后修改人、修订号、创建/修改时间
#   docProps/app.xml    -> 公司、经理、应用程序、模板、总编辑时间
#   docProps/custom.xml -> 用户自定义属性（什么都能塞）
# 我们把这几处清空，然后重新打包。

NS_CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
NS_DC = "http://purl.org/dc/elements/1.1/"
NS_DCTERMS = "http://purl.org/dc/terms/"
NS_DCMITYPE = "http://purl.org/dc/dcmitype/"
NS_XSI = "http://www.w3.org/2001/XMLSchema-instance"
NS_EXT = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
NS_VT = "http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"
NS_CUSTOM = "http://schemas.openxmlformats.org/officeDocument/2006/custom-properties"

# 先注册命名空间前缀，保证 ElementTree 写出来的 XML 还是原来的样子。
ET.register_namespace("cp", NS_CP)
ET.register_namespace("dc", NS_DC)
ET.register_namespace("dcterms", NS_DCTERMS)
ET.register_namespace("dcmitype", NS_DCMITYPE)
ET.register_namespace("xsi", NS_XSI)
ET.register_namespace("vt", NS_VT)
ET.register_namespace("", NS_EXT)  # app.xml 用的是默认命名空间

# 一个中性的固定时间，用来替换原始的创建/修改时间。
NEUTRAL_TIME = "2000-01-01T00:00:00Z"


def _xml_tostring(root):
    """把 ElementTree 对象写回 bytes，并带上 XML 声明。"""
    return ET.tostring(root, encoding="UTF-8", xml_declaration=True)


def _clean_core_xml(data, removed):
    """清理 docProps/core.xml。"""
    root = ET.fromstring(data)

    # 直接清空文字的字段
    blank_tags = {
        "{%s}creator" % NS_DC: "creator(作者)",
        "{%s}lastModifiedBy" % NS_CP: "lastModifiedBy(最后修改人)",
        "{%s}subject" % NS_DC: "subject(主题)",
        "{%s}keywords" % NS_CP: "keywords(关键词)",
        "{%s}category" % NS_CP: "category(分类)",
        "{%s}lastPrinted" % NS_CP: "lastPrinted(最后打印时间)",
    }
    for tag, label in blank_tags.items():
        for element in root.iter(tag):
            if element.text and element.text.strip():
                removed.append(label)
            element.text = ""

    # 修订记录：改成一个中性的固定值
    for element in root.iter("{%s}revision" % NS_CP):
        if element.text and element.text.strip():
            removed.append("revision(修订号)")
        element.text = "1"

    # 创建/修改时间：换成固定值
    for tag, label in (
        ("{%s}created" % NS_DCTERMS, "created(创建时间)"),
        ("{%s}modified" % NS_DCTERMS, "modified(修改时间)"),
    ):
        for element in root.iter(tag):
            removed.append(label)
            element.text = NEUTRAL_TIME

    return _xml_tostring(root)


def _clean_app_xml(data, removed):
    """清理 docProps/app.xml（公司和应用程序信息）。"""
    root = ET.fromstring(data)

    blank_children = {
        "Company": "Company(公司)",
        "Manager": "Manager(经理)",
        "Template": "Template(模板)",
        "TotalTime": "TotalTime(总编辑时间)",
        "AppVersion": "AppVersion(应用版本)",
        "HyperlinkBase": "HyperlinkBase(超链接基准)",
    }
    for child in list(root):
        local_name = child.tag.split("}")[-1]
        if local_name in blank_children:
            if child.text and child.text.strip():
                removed.append(blank_children[local_name])
            child.text = ""

    # Application 保留标签但写一个中性的值，避免某些阅读器报错
    for child in list(root):
        if child.tag.split("}")[-1] == "Application":
            child.text = "Local"

    return _xml_tostring(root)


def _clean_custom_xml(data, removed):
    """清空用户自定义属性，但保留合法的根标签。"""
    root = ET.fromstring(data)
    if len(list(root)) > 0:
        removed.append("custom(自定义属性)")
    for child in list(root):
        root.remove(child)
    return _xml_tostring(root)


def _strip_ooxml(src_path, dst_path, removed):
    """清理 docx / pptx / xlsx。返回一句说明文字。"""
    with zipfile.ZipFile(src_path, "r") as zin:
        names = zin.namelist()
        items = {name: zin.read(name) for name in names}

    if "docProps/core.xml" in items:
        items["docProps/core.xml"] = _clean_core_xml(items["docProps/core.xml"], removed)
    if "docProps/app.xml" in items:
        items["docProps/app.xml"] = _clean_app_xml(items["docProps/app.xml"], removed)
    if "docProps/custom.xml" in items:
        items["docProps/custom.xml"] = _clean_custom_xml(items["docProps/custom.xml"], removed)

    with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as zout:
        for name in names:
            zout.writestr(name, items[name])

    return "已清理 docProps 下的作者 / 公司 / 修订等属性。"


# ---------------------------------------------------------------------------
# 三、图片（JPEG / PNG）
# ---------------------------------------------------------------------------

def _strip_jpeg(src_path, dst_path, removed):
    """
    删除 JPEG 里的 APP1(EXIF/XMP)、APP13(IPTC/Photoshop)、注释段。
    保留 APP0(JFIF) 和 APP14(Adobe 颜色信息)，否则部分图片会变色。
    """
    with open(src_path, "rb") as f:
        data = f.read()

    if not data.startswith(b"\xff\xd8"):
        raise ValueError("不是合法的 JPEG 文件（缺少 FFD8 起始标记）")

    out = bytearray(b"\xff\xd8")
    pos = 2
    total = len(data)

    while pos < total:
        if data[pos] != 0xFF:
            # 结构异常，把剩下的原样接上，尽量不破坏文件
            out += data[pos:]
            break

        start = pos
        while pos < total and data[pos] == 0xFF:
            pos += 1
        if pos >= total:
            break

        marker = data[pos]
        pos += 1

        if marker == 0xD9:                      # EOI 结束
            out += b"\xff\xd9"
            break
        if marker == 0xDA:                      # SOS，后面是图像数据
            out += data[start:]
            break
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:   # 无长度字段的标记
            out += data[start:pos]
            continue

        length = int.from_bytes(data[pos:pos + 2], "big")
        raw_segment = data[start:pos + length]
        payload = data[pos:pos + length]

        if marker == 0xE1 and payload[2:8] == b"Exif\x00\x00":
            removed.append("JPEG EXIF (APP1)")
        elif marker == 0xE1:
            removed.append("JPEG XMP (APP1)")
        elif marker == 0xED:
            removed.append("JPEG IPTC/Photoshop (APP13)")
        elif marker == 0xFE:
            removed.append("JPEG 注释 (COM)")
        else:
            out += raw_segment

        pos += length

    with open(dst_path, "wb") as f:
        f.write(bytes(out))
    return "已删除 JPEG 的 EXIF / XMP / IPTC / 注释段。"


def _strip_png(src_path, dst_path, removed):
    """删除 PNG 里的文本块、EXIF 块和时间戳块。"""
    drop_types = {b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME"}
    type_labels = {
        b"tEXt": "PNG tEXt 文本块",
        b"zTXt": "PNG zTXt 压缩文本块",
        b"iTXt": "PNG iTXt 国际文本块",
        b"eXIf": "PNG eXIf EXIF块",
        b"tIME": "PNG tIME 时间戳块",
    }

    with open(src_path, "rb") as f:
        data = f.read()

    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是合法的 PNG 文件（签名不对）")

    out = bytearray(data[:8])
    pos = 8
    while pos + 8 <= len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        chunk_type = data[pos + 4:pos + 8]
        chunk_total = 12 + length          # 长度(4)+类型(4)+数据+CRC(4)
        chunk = data[pos:pos + chunk_total]
        if chunk_type in drop_types:
            removed.append(type_labels.get(chunk_type, chunk_type.decode("ascii", "replace")))
        else:
            out += chunk
        pos += chunk_total
        if chunk_type == b"IEND":
            break

    with open(dst_path, "wb") as f:
        f.write(bytes(out))
    return "已删除 PNG 的文本 / EXIF / 时间戳块。"


# ---------------------------------------------------------------------------
# 四、PDF
# ---------------------------------------------------------------------------
#
# 说明（这也是本期的一个已知限制，见 SELF_TEST.md）：
# 标准库无法像第三方库那样完整重排 PDF 的对象表。我们的做法是：
#   1. 找到 trailer 里的 /Info 对象，把 Author / Creator / Producer 等
#      字符串值原地替换成等长空格（长度不变 => 交叉引用表偏移不变 => 文件不坏）
#   2. 找到 XMP 元数据流，把流内容原地替换成等长空格
# 如果这些信息被压缩进「对象流」里，明文搜索就找不到，无法清理。
# 这是纯标准库方案的固有限制，已在 SELF_TEST.md 中明确记录。

PDF_INFO_KEYS = [
    b"Author", b"Creator", b"Producer", b"Title", b"Subject",
    b"Keywords", b"CreationDate", b"ModDate", b"Company",
    b"Manager", b"LastModifiedBy",
]


def _blank_pdf_literal_strings(block, removed):
    """把 PDF 字典里的 (字符串) 和 <十六进制串> 原地换成等长空格。"""
    buffer = bytearray(block)
    for key in PDF_INFO_KEYS:
        # (...) 普通字符串
        pattern = re.compile(rb"/" + re.escape(key) + rb"\s*\(([^)]*)\)", re.DOTALL)
        for match in pattern.finditer(bytes(buffer)):
            start, end = match.span(1)
            if bytes(buffer[start:end]).strip():
                removed.append(key.decode("ascii", "replace"))
                buffer[start:end] = b" " * (end - start)
        # <...> 十六进制字符串
        hex_pattern = re.compile(rb"/" + re.escape(key) + rb"\s*<([0-9A-Fa-f\s]*)>", re.DOTALL)
        for match in hex_pattern.finditer(bytes(buffer)):
            start, end = match.span(1)
            if bytes(buffer[start:end]).strip():
                removed.append(key.decode("ascii", "replace") + "(hex)")
                buffer[start:end] = b" " * (end - start)
    return bytes(buffer)


def _strip_pdf(src_path, dst_path, removed):
    with open(src_path, "rb") as f:
        data = f.read()

    out = bytearray(data)
    found_info = False

    # 找 trailer 里的 /Info N 0 R，得到信息字典的对象号
    obj_numbers = set()
    for match in re.finditer(rb"/Info\s+(\d+)\s+\d+\s+R", data):
        obj_numbers.add(match.group(1))

    for number in obj_numbers:
        header = re.search(rb"(?:^|\s)" + re.escape(number) + rb"\s+\d+\s+obj\b", data)
        if not header:
            continue
        end = data.find(b"endobj", header.end())
        if end == -1:
            continue
        block = bytes(out[header.end():end])
        new_block = _blank_pdf_literal_strings(block, removed)
        if new_block != block:
            found_info = True
        out[header.end():end] = new_block  # 等长替换，不影响 xref 偏移

    # 清理 XMP 元数据流（内容换成等长空格）
    stripped_xmp = False
    for stream_match in re.finditer(rb"stream\r?\n", data):
        content_start = stream_match.end()
        content_end = data.find(b"endstream", content_start)
        if content_end == -1:
            continue
        content = bytes(out[content_start:content_end])
        lowered = content.lower()
        if b"xmpmeta" in lowered or b"xpacket" in lowered or b"adobe:ns:meta" in lowered:
            blank = bytes(10 if byte == 0x0A else 13 if byte == 0x0D else 0x20 for byte in content)
            out[content_start:content_end] = blank
            removed.append("XMP")
            stripped_xmp = True

    with open(dst_path, "wb") as f:
        f.write(bytes(out))

    note = "已尽力清除 PDF 的 /Info 与 XMP 元数据。"
    if not found_info and not stripped_xmp:
        note += "（未找到明文元数据，可能被压缩在对象流里，标准库无法处理。）"
    elif not found_info:
        note += "（未发现明文 /Info 字典，可能被压缩。）"
    return note


# ---------------------------------------------------------------------------
# 五、命令行入口：方便单独验证
# ---------------------------------------------------------------------------

def main(argv):
    if len(argv) != 3:
        print("用法: python metadata.py 输入文件 输出文件")
        print("示例: python metadata.py 原始.docx 清理后.docx")
        return 2
    result = strip_metadata(argv[1], argv[2])
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
