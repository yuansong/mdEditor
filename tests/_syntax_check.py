# -*- coding: utf-8 -*-
"""mdEditor 内核语法检查（跨平台、无硬编码路径，可被 CI 直接调用）。

抽取 src/editor.html 中所有**内联** <script> 块（不含带 src= 的外部脚本，
如 katex.min.js），拼接后用 `node --check` 校验语法。期望退出码 0。

用法：
    python tests/_syntax_check.py            # 自动探测 node
    NODE=/path/to/node python tests/_syntax_check.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EDITOR_HTML = os.path.join(ROOT, "src", "editor.html")


def _find_node():
    env = os.environ.get("NODE")
    if env and os.path.exists(env):
        return env
    found = shutil.which("node")
    if found:
        return found
    # 常见 Windows 路径兜底（不影响 CI / 标准环境）
    for cand in (
        r"C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe",
    ):
        if os.path.exists(cand):
            return cand
    return None


def main():
    if not os.path.exists(EDITOR_HTML):
        print("[syntax] 未找到 src/editor.html: %s" % EDITOR_HTML)
        return 1

    with open(EDITOR_HTML, "r", encoding="utf-8") as f:
        html = f.read()

    # 仅匹配无属性的 <script>...</script>，自动排除 <script src=...>
    blocks = re.findall(r"<script>([\s\S]*?)</script>", html)
    if not blocks:
        print("[syntax] 未找到任何内联 <script> 块")
        return 1

    code = "\n;\n".join(blocks)
    node = _find_node()
    if not node:
        print("[syntax][warn] 未找到 node，跳过语法检查（请在 PATH 中安装 Node.js 22.x）")
        return 0

    fd, path = tempfile.mkstemp(suffix=".js", prefix="mdeditor_syntax_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        r = subprocess.run([node, "--check", path],
                           capture_output=True, text=True, encoding="utf-8")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass

    if r.returncode == 0:
        print("[syntax] PASS：editor.html 内联脚本语法检查通过（%d 个块，%d 字符）"
              % (len(blocks), len(code)))
        return 0
    print("[syntax] FAIL：editor.html 语法错误\n%s" % (r.stderr or r.stdout))
    return 1


if __name__ == "__main__":
    sys.exit(main())
