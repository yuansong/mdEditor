# 汇总 smoke 测试结果（动态扫描 tests/_smokeNN.txt，不再写死范围）
import os
import re

here = os.path.dirname(os.path.abspath(__file__))
pat = re.compile(r"^_smoke(\d+)\.txt$")
files = []
for name in os.listdir(here):
    m = pat.match(name)
    if m:
        files.append((int(m.group(1)), name))
files.sort()

fails, passes, empty = [], 0, []
for _n, name in files:
    p = os.path.join(here, name)
    got = 0
    with open(p, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("PASS"):
                passes += 1
                got += 1
            elif line.startswith("FAIL"):
                fails.append(name + " " + line.strip())
    if got == 0:
        empty.append(name)

print("SMOKE FILES:", ", ".join(n for _n, n in files))
print("PASS=", passes, " FAIL=", len(fails),
      (" EMPTY=" + ",".join(empty)) if empty else "")
for x in fails:
    print(x)
with open(os.path.join(here, "_summary.txt"), "w", encoding="utf-8") as fh:
    fh.write(f"files={len(files)} PASS={passes} FAIL={len(fails)}\n"
             + ("EMPTY=" + ",".join(empty) + "\n" if empty else "")
             + "\n".join(fails))
