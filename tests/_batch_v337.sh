#!/bin/sh
# v3.37 验证批次：先 rename 旧结果文件（rename 不触发 safe-delete 配额），再逐个跑
export PATH="/usr/bin:/bin:$PATH"
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd /e/WorkBuddy/md-editor || exit 1
LOG=tests/_batch_v337.txt
: > "$LOG"

for p in _m105 _m105c _m104 _m71 _m96 _m89 _m52 _m86_bi; do
  b=$(basename "$p")
  # 结果文件可能叫 _mNNN.txt 或 _mNNN_xxx.txt 形式
  for r in tests/${b}.txt; do
    if [ -f "$r" ]; then mv "$r" "$r.old2" 2>/dev/null; fi
  done
  echo "===== $p =====" >> "$LOG"
  "$PY" tests/_runner.py "tests/${b}.py" >> "$LOG" 2>&1
  echo "exit=$?" >> "$LOG"
done
echo "BATCH DONE" >> "$LOG"
