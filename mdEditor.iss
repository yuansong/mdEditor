; mdEditor 安装包脚本（Inno Setup）
; 打包当前 onedir 产物 dist143\mdEditor\ 为正式 Windows 安装程序
; 用法：ISCC.exe mdEditor.iss  → 输出 installer\mdEditor-setup-<版本>.exe

#define MyAppName "mdEditor"
; 版本可由 CI 通过 /DMyAppVersion= 覆盖；本地默认值与 src/config.py 同步
#ifndef MyAppVersion
#define MyAppVersion "3.48.39"
#endif
#define MyAppPublisher "mdEditor"
#define MyAppURL "https://github.com/yuansong/mdEditor"
#define MyAppExeName "mdEditor.exe"
; 源目录：PyInstaller onedir 产物（整个文件夹缺一不可）。
; CI 覆盖为 dist\mdEditor；本地默认同样指向 dist\mdEditor。
#ifndef MySrcDir
#define MySrcDir "dist\mdEditor"
#endif
#define MyIco "src\mdeditor.ico"

[Setup]
; 基本信息
AppId={{8F2B6E1A-3C4D-4E5F-9A0B-1C2D3E4F5A6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} - Markdown 编辑器
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

; 安装位置
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; 仅支持 64 位 Windows；装到 Program Files
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible

; 输出
OutputDir=installer
OutputBaseFilename={#MyAppName}-setup-{#MyAppVersion}
SetupIconFile={#MyIco}
UninstallDisplayIcon={#MyIco}
Compression=lzma2/max
SolidCompression=yes
; 大包：放宽单个文件体积相关限制
DiskSpanning=no
; 安装包自身图标与语言
WizardStyle=modern

; 权限与体验
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
DirExistsWarning=no
DisableDirPage=auto
AlwaysShowComponentsList=no
; 单实例安装，避免重复运行
SetupMutex={#MyAppName}-setup-mutex

[Languages]
Name: "Chinese"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加任务"; Flags: unchecked
Name: "quicklaunchicon"; Description: "创建快速启动栏快捷方式"; GroupDescription: "附加任务"; Flags: unchecked

[Files]
; 递归打包整个 onedir 产物（含 Qt/Python/Chromium 运行时 + 内核 + 资源）
Source: "{#MySrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{#MyIco}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"; IconFilename: "{#MyIco}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{#MyIco}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{#MyIco}"; Tasks: quicklaunchicon

[Run]
; 完成页可选立即运行
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时清理可能由程序生成的用户数据目录（可选，谨慎）
Type: filesandordirs; Name: "{app}\_empty"
