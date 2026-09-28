# -*- coding: utf-8 -*-
"""Detached launcher for the full regression (avoids the 120s background-task kill)."""
import subprocess, sys, os

here = os.path.dirname(os.path.abspath(__file__))
DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
log = open(os.path.join(here, "_full_out_wrap.txt"), "w", encoding="utf-8")
p = subprocess.Popen(
    ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
     "-File", os.path.join(here, "_run_full.ps1")],
    stdout=log, stderr=subprocess.STDOUT, cwd=here,
    creationflags=DETACHED)
print("LAUNCHED PID", p.pid)
