"""
start.bat 手工验证脚本
=====================

不是测试框架，是一条可反复执行的验证命令：

    python verify_start_bat.py

它会用 `cmd /c start.bat`（等价于双击）启动服务，等首页能访问后打印结果，
再自动关掉服务，并把 start.bat 的真实输出打印出来。

注意：它会生成 config.ini 和 data/（如果还没有的话），这是正常现象。
"""
import os
import subprocess
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))


def main():
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        ["cmd", "/c", "start.bat"],
        cwd=BASE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        for _ in range(40):
            time.sleep(0.25)
            try:
                with urllib.request.urlopen("http://127.0.0.1:8000/", timeout=2) as response:
                    print("HTTP_STATUS=%d" % response.status)
                    print("CONTENT_LENGTH=%d" % len(response.read()))
                    break
            except OSError:
                continue
        else:
            print("HTTP_STATUS=NOT_REACHABLE")
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    output = process.stdout.read().decode("utf-8", "replace")
    print("--- start.bat 完整输出 ---")
    print(output)


if __name__ == "__main__":
    main()
