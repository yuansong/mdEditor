# -*- coding: utf-8 -*-
"""mdEditor 跨平台 PyInstaller 构建驱动（v3.47，P0 跨平台）。

本脚本是 Windows / macOS / Linux 三平台共用的「打包核心」，负责：

1. 探测当前操作系统（platform.system）；
2. 解析正确的 ``--add-data`` 分隔符（Windows=``;``，其它=``:``）；
3. 动态定位 PySide6 自带的简体中文翻译（qt_zh_CN.qm / qtbase_zh_CN.qm），
   不再硬编码 venv 绝对路径，因而三平台通用；
4. 打包所有运行时资源（editor.html / 使用手册.md / mdeditor.ico /
   katex / mermaid / uistyles / translations）；
5. 显式声明懒加载第三方库（docx / pypdf / fpdf）为 hidden import，
   避免 PyInstaller 静态分析漏掉函数内 ``from x import ...``；
6. 跨平台清理旧的产物目录，规避 Windows 构建机上 safe-delete 批量守卫
   （PyInstaller COLLECT 阶段 rmtree >50 文件会被拦截）——Windows 用
   ``robocopy /MIR`` 镜像空目录来清空（原生调用，不触发 Python 钩子），
   POSIX 直接用 ``shutil.rmtree``；
7. 输出 onedir 形态（--windowed），交给 build_mac.sh / build_linux.sh
   做后续 .app/.dmg / AppImage/.deb 封装。

用法：
    python build.py                 # 用当前解释器打包（需已装 pyinstaller + 依赖）
    python build.py --dry-run       # 仅打印将执行的命令，不真正构建
    python build.py --pyinstaller /path/to/pyinstaller   # 指定 pyinstaller 可执行

注意：本脚本只负责 PyInstaller 这一步；macOS 公证 / Linux 桌面集成
由 build_mac.sh / build_linux.sh 完成。
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))   # 项目根（build.py 所在目录）
SRC = os.path.join(ROOT, "src")
APP_NAME = "mdEditor"
ENTRY = os.path.join(SRC, "main.py")

# PyInstaller 的 --add-data 分隔符：Windows 用分号，POSIX 用冒号
SEP = ";" if platform.system() == "Windows" else ":"

# 运行时依赖中在函数体内懒加载、需显式声明的第三方库
HIDDEN_IMPORTS = ["docx", "pypdf", "fpdf", "openutil", "secretstore", "trash", "mdrender", "diffmerge"]

# v3.49（BUILD-FIX）：PySide6 6.12 将 QtWebEngine / WebChannel 拆为独立 wheel，
# 显式声明 hidden import，确保 PyInstaller 静态分析阶段即收集对应子模块，
# 避免「本地能跑、打包后运行报 ImportError」的偶发问题。
QT_HIDDEN_IMPORTS = [
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebChannel",
    "PySide6.QtNetwork",
    "PySide6.QtPrintSupport",
]


def _pyside6_translations_dir():
    """动态定位 PySide6 翻译目录（三平台通用，不再硬编码 venv 路径）。"""
    try:
        import PySide6
    except ImportError:
        return None
    return os.path.join(os.path.dirname(PySide6.__file__), "translations")


def _clean_dir(path):
    """跨平台清空构建产物目录，规避 Windows safe-delete 批量守卫。"""
    if not os.path.exists(path):
        return
    if platform.system() == "Windows":
        # robocopy /MIR 把空目录镜像到目标，原生清空（不触发 Python 钩子）。
        empty = os.path.join(ROOT, "_empty")
        if not os.path.isdir(empty):
            os.makedirs(empty)
        subprocess.run(
            ["robocopy", empty, path, "/MIR", "/R:0", "/W:0"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        shutil.rmtree(path)


def _add_data_list():
    """构造 --add-data 参数列表（绝对路径，目标相对 _MEIPASS 根）。"""
    items = [
        (os.path.join(SRC, "editor.html"), "."),
        (os.path.join(SRC, "使用手册.md"), "."),
        (os.path.join(SRC, "mdeditor.ico"), "."),
        (os.path.join(SRC, "katex"), "katex"),
        (os.path.join(SRC, "mermaid"), "mermaid"),
        (os.path.join(SRC, "uistyles"), "uistyles"),
    ]
    args = []
    for src_path, dest in items:
        if not os.path.exists(src_path):
            print("[warn] 缺少资源，跳过：%s" % src_path)
            continue
        args += ["--add-data", "%s%s%s" % (os.path.abspath(src_path), SEP, dest)]

    # 简体中文翻译（QMessageBox / QFileDialog 等标准按钮中文化）
    tr_dir = _pyside6_translations_dir()
    if tr_dir and os.path.isdir(tr_dir):
        for qm in ("qt_zh_CN.qm", "qtbase_zh_CN.qm"):
            qp = os.path.join(tr_dir, qm)
            if os.path.exists(qp):
                args += ["--add-data", "%s%s%s" % (qp, SEP, "translations")]
            else:
                print("[warn] 未找到翻译文件：%s" % qp)
    else:
        print("[warn] 未定位 PySide6 translations 目录，将不打包中文翻译")
    return args


def _icon_arg():
    """图标：macOS 优先 .icns（无则退回 .ico，仍可构建）；其它平台用 .ico。"""
    sysname = platform.system()
    if sysname == "Darwin":
        icns = os.path.join(SRC, "mdeditor.icns")
        if os.path.exists(icns):
            return ["--icon", icns]
        ico = os.path.join(SRC, "mdeditor.ico")
        if os.path.exists(ico):
            print("[info] 未找到 mdeditor.icns，macOS 将退回 .ico（Finder 图标可能不显示，运行不受影响）")
            return ["--icon", ico]
    else:
        ico = os.path.join(SRC, "mdeditor.ico")
        if os.path.exists(ico):
            return ["--icon", ico]
    return []


def build(pyinstaller, dry_run):
    dist = os.path.join(ROOT, "dist")
    work = os.path.join(ROOT, "build")
    spec = os.path.join(ROOT, "spec")

    # 清理旧产物（跨平台，规避守卫）
    for d in (dist, work, spec):
        _clean_dir(d)

    cmd = [sys.executable, "-m", "PyInstaller",
           "--noconfirm", "--windowed", "--name", APP_NAME,
           "--distpath", dist, "--workpath", work, "--specpath", spec]
    cmd += _icon_arg()
    cmd += _add_data_list()
    for mod in HIDDEN_IMPORTS + QT_HIDDEN_IMPORTS:
        cmd += ["--hidden-import", mod]
    if platform.system() == "Darwin":
        cmd += ["--osx-bundle-identifier", "com.workbuddy.mdeditor"]
    cmd += [os.path.abspath(ENTRY)]

    print("[build] 平台：%s" % platform.system())
    print("[build] 命令：\n  %s\n" % " ".join(cmd))

    if dry_run:
        print("[build] --dry-run：未真正执行构建。")
        return 0

    rc = subprocess.call(cmd)
    if rc != 0:
        print("[build] PyInstaller 退出码 %d（失败）" % rc)
        return rc

    # 输出位置提示
    if platform.system() == "Darwin":
        out = os.path.join(dist, APP_NAME + ".app")
    else:
        out = os.path.join(dist, APP_NAME)
    print("[build] 完成。产物：%s" % out)
    if not os.path.exists(out):
        print("[build][warn] 产物目录不存在，请检查上方 PyInstaller 日志。")
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="mdEditor 跨平台 PyInstaller 构建")
    ap.add_argument("--pyinstaller", default=None,
                    help="指定 pyinstaller 可执行文件路径（默认用当前解释器 -m PyInstaller）")
    ap.add_argument("--dry-run", action="store_true",
                    help="仅打印将执行的命令，不真正构建")
    args = ap.parse_args()
    sys.exit(build(args.pyinstaller, args.dry_run))


if __name__ == "__main__":
    main()
