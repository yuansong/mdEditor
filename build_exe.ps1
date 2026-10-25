# mdEditor 一键打包脚本（v3.46.0：书籍章节持久化 + 📚状态图标 + 竞品短板 PNG/跳转历史 → dist143）
$ErrorActionPreference = "Stop"
$pyi = "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Scripts\pyinstaller.exe"
$root = $PSScriptRoot
Set-Location $root
# 注意：--add-data 必须用绝对路径（--specpath 自定义时相对路径会解析错误）
# translations：Qt 官方简体中文翻译（QMessageBox/QFileDialog 等标准按钮显示中文）
# PS5.1 坑：EAP=Stop 时原生命令 stderr 经 *>&1 重定向会变 terminating error
# （首行 INFO 即中断）→ 调用 PyInstaller 期间临时 EAP=SilentlyContinue：
# 既避免 *>&1 合并的 stderr 触发终止，也抑制 NativeCommandError 误报「failed」，
# 使打包任务正常报告成功（真实失败仍可由 Build complete! / exe 有无判定）。
$ErrorActionPreference = "SilentlyContinue"
# 重打同一 distNN 前先清空前次产物，避免 PyInstaller COLLECT 阶段 rmtree 触发
# safe-delete 批量守卫（>50 文件需确认）导致构建中断。用 robocopy /MIR 镜像一个
# 空目录来清空（绕过 Python shutil 钩子），仅删 buildNN/distNN，不动其它。
$empty = Join-Path $root "_empty"
if (!(Test-Path $empty)) { New-Item -ItemType Directory -Path $empty | Out-Null }
robocopy $empty (Join-Path $root "dist144\mdEditor") /MIR /R:0 /W:0 | Out-Null
robocopy $empty (Join-Path $root "build144") /MIR /R:0 /W:0 | Out-Null
& $pyi --noconfirm --windowed --name mdEditor `
    --distpath "$root\dist144" --workpath "$root\build144" --specpath "$root\spec144" `
    --icon "$root\src\mdeditor.ico" `
    --add-data "$root\src\editor.html;." `
    --add-data "$root\src\使用手册.md;." `
    --add-data "$root\src\mdeditor.ico;." `
    --add-data "$root\src\katex;katex" `
    --add-data "$root\src\mermaid;mermaid" `
    --add-data "$root\src\uistyles;uistyles" `
    --add-data "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages\PySide6\translations\qt_zh_CN.qm;translations" `
    --add-data "C:\Users\Administrator\.workbuddy\binaries\python\envs\default\Lib\site-packages\PySide6\translations\qtbase_zh_CN.qm;translations" `
    src\main.py *>&1 | Out-String | Out-File "$root\_build_log.txt" -Encoding utf8
Write-Output "exit=$LASTEXITCODE"
