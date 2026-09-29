"""
配置模块
========

负责读取 config.ini。
管理页的令牌（token）不写死在代码里，而是：
    1. 优先读环境变量 LDSG_ADMIN_TOKEN
    2. 其次读 config.ini 里的 admin_token
    3. 如果两边都没有，就自动生成一个随机令牌并写回 config.ini

这样双击 start.bat 第一次启动时，会自动得到一个令牌，
并且打印在控制台上，用户不用自己编。
"""

import configparser
import os
import secrets


def load_config(base_dir):
    """
    读取（必要时创建）配置文件，返回一个普通字典。

    base_dir：项目所在目录，用来拼出 config.ini 的路径。
    """
    config_path = os.path.join(base_dir, "config.ini")

    parser = configparser.ConfigParser()
    parser["server"] = {
        "host": "127.0.0.1",   # 只允许本机访问
        "port": "8000",
    }
    parser["admin"] = {
        "admin_token": "",
    }
    parser["security"] = {
        "ip_hmac_key": "",
    }

    changed = False
    if os.path.exists(config_path):
        parser.read(config_path, encoding="utf-8")

    # --- 管理令牌：环境变量优先 ---
    token = (os.environ.get("LDSG_ADMIN_TOKEN") or "").strip()
    if not token:
        token = parser["admin"].get("admin_token", "").strip()
    if not token:
        token = secrets.token_urlsafe(12)
        changed = True
    parser["admin"]["admin_token"] = token

    # --- 给 IP 做 HMAC 用的密钥，避免明文存 IP ---
    if not parser["security"].get("ip_hmac_key", "").strip():
        parser["security"]["ip_hmac_key"] = secrets.token_hex(16)
        changed = True

    if changed or not os.path.exists(config_path):
        with open(config_path, "w", encoding="utf-8") as f:
            parser.write(f)

    host = (os.environ.get("LDSG_HOST") or parser["server"].get("host", "127.0.0.1")).strip()
    port_text = (os.environ.get("LDSG_PORT") or parser["server"].get("port", "8000")).strip()
    try:
        port = int(port_text)
    except ValueError:
        port = 8000

    return {
        "config_path": config_path,
        "host": host,
        "port": port,
        "admin_token": parser["admin"]["admin_token"],
        "ip_hmac_key": parser["security"]["ip_hmac_key"],
    }
