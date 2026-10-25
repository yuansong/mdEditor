# mdEditor macOS 构建、测试与适配指南

> 适用版本：v3.47+（已完成跨平台代码改造）。本文教你如何拿到 macOS 版 mdEditor 并做适配验证。

## 一、最快拿到的 Mac 版（GitHub Actions 自动构建）

仓库已配置 `.github/workflows/build-mac.yml`：每次 push 到 `main` 或手动 Run workflow，
都会在 GitHub 托管的 macOS 真机（Apple 硬件，符合 macOS 许可）上自动构建，并产出可下载产物：

- `mdEditor-macOS-dmg`：分发镜像（双击挂载，把 mdEditor.app 拖到 /Applications）
- `mdEditor-macOS-app`：单独的 .app 包
- `mdEditor-macOS-build-logs`：PyInstaller 日志（构建失败时排查用）

> 注意：CI 默认做 **ad-hoc 签名（无 Apple 开发者证书）**，下载的 .app 未经公证，
> 在其它 Mac 上首次打开会被 Gatekeeper 拦截。绕过方式（任选其一）：
> ```bash
> # 方式一：移除隔离标志（推荐）
> xattr -dr com.apple.quarantine /Applications/mdEditor.app
> # 方式二：右键「打开」-> 在弹窗里点「打开」
> ```

## 二、本地构建（你有 Mac 时）

前置：Python 3.13、Xcode Command Line Tools（`xcode-select --install`）、可选 Homebrew。
```bash
git clone <repo> && cd mdEditor-oss
bash build_mac.sh                 # ad-hoc 签名 + 打 dmg 到 installer/mdEditor-macOS.dmg
# 用真证书签名（需 Apple Developer ID Application 证书）：
MACOS_CERT_ID="Developer ID Application: Your Name (TEAMID)" bash build_mac.sh
```

## 三、公证（正式发布给用户前必做）

ad-hoc 签名无法消除 Gatekeeper 拦截，正式分发必须公证：
```bash
# 1) 一次性把账号存进钥匙串（免明文密码）
xcrun notarytool store-credentials "mdEditor" \
    --apple-id you@icloud.com --team-id TEAMID --password <app-specific-password>
# 2) 构建 + 公证 + 装订票据
NOTARIZE=1 MACOS_CERT_ID="Developer ID Application: ..." \
    APPLE_ID=you@icloud.com APPLE_TEAM_ID=TEAMID APPLE_APP_PASSWORD=<pwd> \
    bash build_mac.sh
```
公证必需的关键授权已内置在 `macos/entitlements.plist`：`allow-jit`、
`allow-unsigned-executable-memory`、`disable-library-validation` —— 这是 QtWebEngine
在 macOS hardened runtime 下能正常运行的前提，缺了会导致启动后白屏/崩溃。

## 四、架构说明

CI 默认用 `macos-13`（Intel x86_64）runner。PySide6 官方 wheel 为 universal2，
因此产出的 .app 在 Apple Silicon（M 系列）上以原生方式运行（无需 Rosetta）。
若需更小体积的纯 arm64 包，把 workflow 的 `runs-on` 改为 `macos-14` / `macos-latest`（arm64）即可。

## 五、重点适配验证清单（Mac 上要实测的项）

代码层已做平台守卫，下列功能在 Mac 上会自动走 Darwin 分支，请实测确认：

| 功能 | Mac 实现 | 验证点 |
|------|----------|--------|
| AI Key 存储 | Keychain（security CLI） | 设置 Key 后重启仍在 |
| 删除文件 | ~/.Trash | 删除后能在废纸篓找回 |
| 打开文件/文件夹 | open 命令 | 菜单「在 Finder 中显示」 |
| 侧栏盘符/挂载点 | /Volumes | 外接盘、移动硬盘出现 |
| 无边框窗口 | 强制系统原生窗口（mactitlebar 守卫） | 标题栏为 macOS 原生 |
| 启动字体 | PingFang SC 回退 | 中文渲染正常 |
| 单实例 | QLocalServer | 二次打开转发到已运行实例 |
| WebEngine 渲染 | QtWebEngine | KaTeX / Mermaid / 预览正常 |
| 应用图标 | src/mdeditor.icns | Finder / 坞站图标显示 |

发现 Mac 专属问题时，请在此文件补充记录或提 issue。
