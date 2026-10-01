#!/bin/sh
# v3.37b 回归批次（FMT-14/15 + 悬浮栏文案）：先 rename 旧结果文件（rename 不触发 safe-delete 配额），再逐个跑
export PATH="/usr/bin:/bin:$PATH"
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd /e/WorkBuddy/md-editor || exit 1
LOG=tests/_batch_v337b.txt
: > "$LOG"

for p in _m101 _m83 _m81_linefmt2 _m84_toggle _m85_toggle2 _m92 _m105 _m105c _m105d _m106 _m104 _m107 _m89 _m52; do
  b=$(basename "$p")
  for r in tests/${b}.txt; do
    if [ -f "$r" ]; then mv "$r" "$r.old3" 2>/dev/null; fi
  done
  echo "===== $p =====" >> "$LOG"
  "$PY" tests/_runner.py "tests/${p}.py" >> "$LOG" 2>&1
  echo "exit=$?" >> "$LOG"
done
echo "BATCH DONE" >> "$LOG"
