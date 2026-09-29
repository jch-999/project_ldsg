@echo off
rem ============================================================
rem  课程资料共享站 启动脚本
rem  双击这个文件即可启动，不需要敲任何命令行参数。
rem ============================================================
chcp 65001 >nul
setlocal
cd /d "%~dp0"

set "PYEXE="

rem 优先用 Windows 自带的 py 启动器，找不到再试 python
where py >nul 2>nul
if %errorlevel%==0 set "PYEXE=py"

if not defined PYEXE (
    where python >nul 2>nul
    if %errorlevel%==0 set "PYEXE=python"
)

if not defined PYEXE (
    echo.
    echo 没有检测到 Python。请先安装 Python 3，安装时记得勾选 "Add Python to PATH"。
    echo 下载地址: https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo 正在启动课程资料共享站，请稍等...
echo.

%PYEXE% app.py

echo.
echo 服务已退出。
pause
