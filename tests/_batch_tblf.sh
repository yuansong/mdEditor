#!/bin/sh
# TBL-F 回归批次：rename 旧结果文件（绕开 safe-delete 配额），再逐个跑
export PATH="/usr/bin:/bin:$PATH"
PY="C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
cd /e/WorkBuddy/md-editor || exit 1
LOG=tests/_batch_tblf.txt
: > "$LOG"

for p in _m29a _m29p _m78 _m32 _m34 _m34b _m77 _m76_x _m104 _m52 _m101 _m83 _m110 _m109; do
  case "$p" in
    _m76_x) f="_m76"; probe="_m76.py" ;;
    *) f="$p"; probe="$p.py" ;;
  esac
  for r in tests/${f}.txt; do
    if [ -f "$r" ]; then mv "$r" "$r.tblf" 2>/dev/null; fi
  done
  echo "===== $probe =====" >> "$LOG"
  "$PY" tests/_runner.py "tests/$probe" >> "$LOG" 2>&1
  echo "exit=$?" >> "$LOG"
done
echo "BATCH DONE" >> "$LOG"
