# mdEditor 一键打包脚本（v3.38 批次之八：主工具栏隐藏后的展开入口 TB-1 → dist64）
$ErrorActionPreference = "Stop"
$pyi = "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\pyinstaller.exe"
$root = $PSScriptRoot
Set-Location $root
# 注意：--add-data 必须用绝对路径（--specpath 自定义时相对路径会解析错误）
# translations：Qt 官方简体中文翻译（QMessageBox/QFileDialog 等标准按钮显示中文）
# PS5.1 坑：EAP=Stop 时原生命令 stderr 经 *>&1 重定向会变 terminating error
# （首行 INFO 即中断）→ 调用 PyInstaller 期间必须临时 EAP=Continue
$ErrorActionPreference = "Continue"
& $pyi --noconfirm --windowed --name mdEditor `
    --distpath dist64 --workpath build64 --specpath spec64 `
    --icon "$root\src\mdeditor.ico" `
    --add-data "$root\src\editor.html;." `
    --add-data "$root\src\mdeditor.ico;." `
    --add-data "$root\src\katex;katex" `
    --add-data "$root\src\mermaid;mermaid" `
    --add-data "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages\PySide6\translations\qt_zh_CN.qm;translations" `
    --add-data "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages\PySide6\translations\qtbase_zh_CN.qm;translations" `
    src\main.py *>&1 | Out-String | Out-File "$root\_build_log.txt" -Encoding utf8
Write-Output "exit=$LASTEXITCODE"
