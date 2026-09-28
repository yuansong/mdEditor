# mdEditor full regression runner.
# NOTE: keep this file pure ASCII. PowerShell 5.1 reads .ps1 without a BOM as
# ANSI, so non-ASCII comments can decode into stray quote/brace bytes and break
# parsing (this bit us with the v3.28 verdict rewrite).
$ErrorActionPreference = "Continue"
$root = "E:\WorkBuddy\md-editor"
Set-Location $root
$venv = "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\python.exe"
$node = "C:\Users\Administrator\.workbuddy\binaries\node\versions\22.22.2-3\node.exe"

$log = "$root\tests\_full_out.txt"
$fail = @()

# Every step is judged by BOTH the exit code and a success marker in the output.
# Counting PASS/FAIL lines alone misses crashes: when the core script throws,
# _summarize.py still prints PASS=N FAIL=0 (false green), so check separately.
"=== syntax (editor.html inline script) ===" | Set-Content $log -Encoding UTF8
$syn = & $venv tests\_syntax_check.py 2>&1
$syn | Add-Content $log -Encoding UTF8
$synText = $syn -join "`n"
if ($LASTEXITCODE -ne 0 -or ($synText -notmatch "returncode=0")) { $fail += "syntax" }

"=== core ===" | Add-Content $log -Encoding UTF8
$core = & $node tests\test_core.js 2>&1
$core | Add-Content $log -Encoding UTF8
$coreText = $core -join "`n"
if ($LASTEXITCODE -ne 0 -or ($coreText -notmatch "ALL TESTS PASSED")) { $fail += "core" }

"=== probes ===" | Add-Content $log -Encoding UTF8
$probe = & $venv tests\_probe25_export.py 2>&1
$probe | Add-Content $log -Encoding UTF8
$probeText = $probe -join "`n"
if ($probeText -notmatch "PROBE25 DONE") { $fail += "probe25-incomplete" }
if ($probeText -match '"FAIL"') { $fail += "probe25-fail" }

# v3.29 feature probes (table caption / quote block rework), same verdict rules.
foreach ($m in "m29a", "m29b") {
    & $venv tests\_runner.py ("tests\_" + $m + ".py") | Out-Null
    Start-Sleep -Seconds 5
    $txt = Get-Content ("tests\_" + $m + ".txt") -Encoding UTF8 -ErrorAction SilentlyContinue
    $passN = @($txt | Where-Object { $_ -like "PASS*" }).Count
    $failN = @($txt | Where-Object { $_ -like "FAIL*" }).Count
    if ($failN -gt 0) { $fail += ($m + "-fail(" + $failN + ")") } elseif ($passN -eq 0) { $fail += ($m + "-crash") }
    ($m + " done PASS=" + $passN + " FAIL=" + $failN) | Add-Content $log -Encoding UTF8
}

"=== smoke ===" | Add-Content $log -Encoding UTF8
foreach ($n in 11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32) {
    & $venv tests\_runner.py ("tests\_smoke" + $n + ".py") | Out-Null
    # v3.28: back-to-back QWebEngine GUI launches can deadlock the next process
    # while GPU / shared-memory state is being released, so leave a short gap.
    Start-Sleep -Seconds 5
    $txt = Get-Content ("tests\_smoke" + $n + ".txt") -Encoding UTF8 -ErrorAction SilentlyContinue
    $passN = @($txt | Where-Object { $_ -like "PASS*" }).Count
    $failN = @($txt | Where-Object { $_ -like "FAIL*" }).Count
    # Judged by the result file, not the exit code: QtWebEngine apps sometimes
    # crash during teardown after writing all results (non-zero exit, clean output).
    # PowerShell 5.1: elseif must stay on the same line as the closing brace.
    if ($failN -gt 0) { $fail += ("smoke" + $n + "-fail(" + $failN + ")") } elseif ($passN -eq 0) { $fail += ("smoke" + $n + "-crash") }
    "smoke$n done PASS=$passN FAIL=$failN" | Add-Content $log -Encoding UTF8
}

"=== summary ===" | Add-Content $log -Encoding UTF8
$sum = & $venv tests\_summarize.py 2>&1
$sum | Add-Content $log -Encoding UTF8
$sumText = $sum -join "`n"
if ($sumText -notmatch "FAIL= 0(\s|$)") { $fail += "smoke-fail" }

# v3.28 final integrity check: confirm every result file exists with FAIL=0.
# The in-loop branches once let a 0/0 case (no result file at all) slip through.
foreach ($n in 11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32) {
    $rf = "tests\_smoke" + $n + ".txt"
    $pp = 0
    $ff = 0
    if (Test-Path $rf) {
        $cl = Get-Content $rf -Encoding UTF8
        foreach ($ln in $cl) {
            if ($ln -like "PASS*") { $pp = $pp + 1 }
            if ($ln -like "FAIL*") { $ff = $ff + 1 }
        }
    }
    if ($pp -eq 0) { $fail += ("smoke" + $n + "-noresult") }
    if ($ff -gt 0) { $fail += ("smoke" + $n + "-hasfail") }
}

"=== verdict ===" | Add-Content $log -Encoding UTF8
if ($fail.Count -gt 0) {
    ("VERDICT: FAILED -> " + ($fail -join ", ")) | Add-Content $log -Encoding UTF8
    exit 1
}
"VERDICT: ALL GREEN" | Add-Content $log -Encoding UTF8
exit 0
