#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
云端版验收脚本（ad-hoc 验证，不是测试套件）
=============================================

用途：起本地 wrangler dev 后，跑这个脚本核验功能与准入机制。
性质：本项目没有 canonical test/lint/build 命令（它是 Workers 应用），
      所以验证方式就是「起本地服务 → 打接口 → 查 D1/R2」。这是针对行为的临时验证，
      不是「测试套件跑绿」。

用法：
    # 终端 A
    npx wrangler d1 execute ldsg --local --file=schema.sql
    npx wrangler dev --port 8789

    # 终端 B
    python verify/verify_cloud.py

退出码：0 = 全部通过；1 = 有失败；2 = 服务未就绪。
"""
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

PORT = int(os.environ.get("LDSG_VERIFY_PORT", "8789"))
BASE = f"http://127.0.0.1:{PORT}"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = F = 0


def ck(name, cond, detail=""):
    global P, F
    if cond:
        P += 1
        print(f"  PASS  {name}")
    else:
        F += 1
        print(f"  FAIL  {name}  {detail}")


def req(path, method="GET", data=None, headers=None, follow=True):
    r = urllib.request.Request(BASE + path, data=data,
                               headers=dict(headers or {}), method=method)
    if not follow:
        class NR(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *a, **k):
                return None
        op = urllib.request.build_opener(NR)
    else:
        op = urllib.request.build_opener()
    try:
        with op.open(r, timeout=30) as resp:
            return resp.status, resp.read(), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)
    except Exception as e:
        return -1, str(e).encode(), {}


def multipart(fields, filename="", content=b""):
    b = "----VerifyBoundary"
    out = io.BytesIO()
    for k, v in fields.items():
        out.write(f"--{b}\r\n".encode())
        out.write(f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode())
        out.write(f"{v}\r\n".encode())
    if filename:
        out.write(f"--{b}\r\n".encode())
        out.write(f'Content-Disposition: form-data; name="file"; '
                  f'filename="{filename}"\r\n'.encode())
        out.write(b"Content-Type: application/octet-stream\r\n\r\n")
        out.write(content + b"\r\n")
    out.write(f"--{b}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={b}"


def d1(sql):
    """查本地 D1。--json 输出里从第一个 '[' 开始解析。"""
    p = subprocess.run(
        f'npx wrangler d1 execute ldsg --local --json --command "{sql}"',
        cwd=ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120, shell=True)
    try:
        return json.loads(p.stdout[p.stdout.index("["):])[0]["results"]
    except Exception:
        return None


def r2_count():
    """本地 R2 对象数：数 .wrangler state 下的 blob 文件。"""
    n = 0
    root = os.path.join(ROOT, ".wrangler", "state", "v3", "r2")
    for _, _, fs in os.walk(root):
        n += len(fs)
    return n


def read_admin_token():
    """从 .dev.vars 读管理令牌（不硬编码，避免与配置不一致造成假失败）。"""
    path = os.path.join(ROOT, ".dev.vars")
    if not os.path.exists(path):
        return ""
    for line in open(path, encoding="utf-8"):
        if line.startswith("ADMIN_TOKEN="):
            return line.split("=", 1)[1].strip()
    return ""


PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n"
ADMIN = read_admin_token()


def main():
    print("=" * 60)
    print("云端版验收（ad-hoc 验证，非测试套件）")
    print("=" * 60)

    print("\n[0] 服务存活")
    st, _, _ = req("/")
    ck("首页 200", st == 200, f"{st}")
    if st != 200:
        print("\n服务未就绪。请先运行：npx wrangler dev --port %d" % PORT)
        return 2

    print("\n[1] 全流程：上传 → 审核 → 详情 → 下载 → 举报")
    mp, ct = multipart({"title": "VERIFY-FLOW", "course_code": "VERI1010",
                        "category": "笔记", "semester": "2026S1",
                        "description": "验收用"}, "verify.pdf", PDF)
    st, _, _ = req("/upload", "POST", mp, {"Content-Type": ct})
    ck("上传 200", st == 200, f"{st}")

    row = d1("SELECT id,status FROM materials WHERE course_code='VERI1010' "
             "ORDER BY created_at DESC LIMIT 1")
    ck("入库且状态 pending", row and row[0]["status"] == "pending", f"{row}")
    mid = row[0]["id"] if row else ""

    lb, lc = multipart({"token": ADMIN})
    st, _, hdr = req("/admin", "POST", lb, {"Content-Type": lc}, follow=False)
    ck("管理登录 303", st == 303, f"{st}")
    c = re.search(r"(ldsg_admin=[^;]+)", hdr.get("Set-Cookie", "") or "")
    ck("拿到会话 cookie", bool(c), f"{hdr.get('Set-Cookie')}")
    cv = c.group(1) if c else ""

    ab, ac = multipart({"action": "approve", "material_id": mid})
    st, _, _ = req("/admin/action", "POST", ab,
                   {"Content-Type": ac, "Cookie": cv}, follow=False)
    ck("审核通过 303", st == 303, f"{st}")
    r = d1(f"SELECT status FROM materials WHERE id='{mid}'")
    ck("状态变为 approved", r and r[0]["status"] == "approved", f"{r}")

    st, body, _ = req(f"/material/{mid}")
    ck("详情页含标题", st == 200 and "VERIFY-FLOW" in body.decode("utf-8", "replace"),
       f"{st}")

    st, body, _ = req(f"/download/{mid}")
    ck("下载内容与上传一致", st == 200 and body.startswith(b"%PDF"),
       f"{st} {body[:8]}")
    r = d1(f"SELECT downloads FROM materials WHERE id='{mid}'")
    ck("下载计数 +1", r and r[0]["downloads"] >= 1, f"{r}")

    for i in range(3):
        rb, rc = multipart({"material_id": mid, "reason": "测试",
                            "detail": str(i)})
        req("/report", "POST", rb, {"Content-Type": rc})
    r = d1(f"SELECT status FROM materials WHERE id='{mid}'")
    ck("举报 3 次自动下架", r and r[0]["status"] == "removed", f"{r}")

    print("\n[2] 预检拒绝：命中的文件必须不落存储、不入库")
    pf = os.path.join(ROOT, "src", "preflight.js")
    original = open(pf, encoding="utf-8").read()
    injected = re.sub(r"export const BLOCKED_KEYWORDS = \[\s*\]",
                      'export const BLOCKED_KEYWORDS = ["VERIFYBLOCKWORD"]',
                      original)
    try:
        assert injected != original, "无法注入测试词（词表结构变了？）"
        open(pf, "w", encoding="utf-8").write(injected)
        time.sleep(6)   # 等 dev server 热重载

        bm = d1("SELECT COUNT(*) AS c FROM materials")[0]["c"]
        br = r2_count()
        bi = d1("SELECT COUNT(*) AS c FROM intercept_log")[0]["c"]

        mp, ct = multipart({"title": "VERIFYBLOCKWORD 危险标题",
                            "course_code": "VERB9999", "category": "其他",
                            "semester": "2026S1", "description": "x"},
                           "blocked.pdf", PDF)
        st, _, _ = req("/upload", "POST", mp, {"Content-Type": ct})
        ck("命中关键词被拒 403", st == 403, f"{st}")
        ck("materials 表未增加",
           d1("SELECT COUNT(*) AS c FROM materials")[0]["c"] == bm)
        ck("R2 未落盘该文件", r2_count() == br, f"{br} -> {r2_count()}")
        ck("intercept_log 增加 1 条",
           d1("SELECT COUNT(*) AS c FROM intercept_log")[0]["c"] == bi + 1)
        il = d1("SELECT action,rule FROM intercept_log "
                "ORDER BY created_at DESC LIMIT 1")
        ck("日志 action=rejected 且记录规则名",
           il and il[0]["action"] == "rejected"
           and "VERIFYBLOCKWORD" in (il[0]["rule"] or ""), f"{il}")
    finally:
        open(pf, "w", encoding="utf-8").write(original)
        time.sleep(5)
        print("      （交付物已还原）")

    print("\n[3] 通道标记：压缩包转强制人审")
    zb, zc = multipart({"title": "VERIFY-ZIP", "course_code": "VERZ1010",
                        "category": "其他", "semester": "2026S1",
                        "description": "x"},
                       "verify.zip", b"PK\x03\x04" + b"\x00" * 40)
    st, _, _ = req("/upload", "POST", zb, {"Content-Type": zc})
    ck("zip 上传 200", st == 200, f"{st}")
    r = d1("SELECT status,intercept_flag FROM materials "
           "WHERE course_code='VERZ1010' ORDER BY created_at DESC LIMIT 1")
    ck("zip 状态 pending（未自动放行）", r and r[0]["status"] == "pending", f"{r}")
    ck("zip 被打上 intercept_flag",
       r and r[0]["intercept_flag"] == "channel:archive", f"{r}")

    print("\n[4] 交付物完整性")
    final = open(pf, encoding="utf-8").read()
    ck("词表已还原为空",
       re.search(r"export const BLOCKED_KEYWORDS = \[\s*\]", final) is not None)
    ck("无测试词残留", "VERIFYBLOCKWORD" not in final)

    deps = json.load(open(os.path.join(ROOT, "package.json"), encoding="utf-8"))
    ck("无运行时依赖（只允许 devDependencies 里的 wrangler）",
       not deps.get("dependencies"), f"{deps.get('dependencies')}")

    print("\n" + "=" * 60)
    print(f"结果：通过 {P} 项，失败 {F} 项")
    print("=" * 60)
    return 1 if F else 0


if __name__ == "__main__":
    sys.exit(main())
