import shutil
# 提取 editor.html 内联脚本做语法检查（node --check）
import os
import re
import subprocess
import sys

here = os.path.dirname(os.path.abspath(__file__))
src = os.path.join(here, "..", "src", "editor.html")
with open(src, encoding="utf-8") as fh:
    html = fh.read()

m = re.search(r"<script>\s*\n(\(function \(\) \{.*?)\n</script>", html, re.S)
if not m:
    m = re.search(r"<script>(.*?)</script>", html, re.S)
if not m:
    print("NO SCRIPT FOUND")
    sys.exit(2)

js = m.group(1)
out = os.path.join(here, "_syntax.js")
with open(out, "w", encoding="utf-8") as fh:
    fh.write(js)

node = shutil.which("node") or "node"
r = subprocess.run([node, "--check", out], capture_output=True, text=True)
log = os.path.join(here, "_syntax.txt")
with open(log, "w", encoding="utf-8") as fh:
    fh.write("returncode=%d\n" % r.returncode)
    fh.write(r.stdout or "")
    fh.write(r.stderr or "")
print("returncode=%d" % r.returncode)
print(r.stderr or "")
