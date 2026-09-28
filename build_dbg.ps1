# mdEditor DEBUG build script (v3.30.13-dbg RZ logging -> dist48dbg, keeps dist48 untouched)
$ErrorActionPreference = "Stop"
$pyi = "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\pyinstaller.exe"
$root = $PSScriptRoot
Set-Location $root
$ErrorActionPreference = "Continue"
& $pyi --noconfirm --windowed --name mdEditor `
    --distpath dist48dbg --workpath build48dbg --specpath spec48dbg `
    --icon "$root\src\mdeditor.ico" `
    --add-data "$root\src\editor.html;." `
    --add-data "$root\src\mdeditor.ico;." `
    --add-data "$root\src\katex;katex" `
    --add-data "$root\src\mermaid;mermaid" `
    --add-data "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages\PySide6\translations\qt_zh_CN.qm;translations" `
    --add-data "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages\PySide6\translations\qtbase_zh_CN.qm;translations" `
    src\main.py *>&1 | Out-String | Out-File "$root\_build_dbg_log.txt" -Encoding utf8
Write-Output "exit=$LASTEXITCODE"
