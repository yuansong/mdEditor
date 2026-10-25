#!/usr/bin/env bash
# =============================================================================
# mdEditor macOS 构建与分发脚本（v3.47，P0 跨平台）
# -----------------------------------------------------------------------------
# 职责：
#   1. 创建 / 复用 Python venv，安装 requirements.txt（PySide6 / PyInstaller / ...）
#   2. 调用 build.py 用 PyInstaller 产出 onedir 的 mdEditor.app
#   3. 对 .app 进行 codesign（未配置证书时做 ad-hoc 签名，足够本地运行；
#      要消除 Gatekeeper「无法打开」必须配置 Apple Developer 证书）
#   4. 用 hdiutil 生成 .dmg 分发镜像
#   5. （可选，需 Apple 开发者账号）xcrun notarytool 公证 + staple
#
# 使用：
#   ./build_mac.sh                 # 构建 + 签名（ad-hoc）+ 打 dmg
#   MACOS_CERT_ID="Developer ID Application: ..." ./build_mac.sh   # 用真证书签名
#   NOTARIZE=1 APPLE_ID=you@icloud.com APPLE_TEAM_ID=XXXX APPLE_APP_PASSWORD=xxxx \
#       ./build_mac.sh             # 构建 + 真证书签名 + 公证 + staple
#
# 前置（用 brew 安装）：
#   brew install python@3.13       # 或系统自带 python3
#   xcode-select --install         # 提供 codesign / hdiutil / xcrun
#
# 注意：QtWebEngine 在 macOS 上要求 .app 被正确签名，且 macOS 11+ 需公证；
#       未公证的 .app 在其它机器上会被 Gatekeeper 拦截（开发者可本地右键「打开」绕过）。
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_NAME="mdEditor"
VENV="${ROOT}/.venv"
INSTALLER_DIR="${ROOT}/installer"
mkdir -p "$INSTALLER_DIR"

echo "==> [mac] 准备 venv"
if [ ! -x "${VENV}/bin/python" ]; then
    "$PYTHON_BIN" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "==> [mac] PyInstaller 构建 .app"
python build.py

APP_BUNDLE="${ROOT}/dist/${APP_NAME}.app"
if [ ! -d "$APP_BUNDLE" ]; then
    echo "!! 未找到 $APP_BUNDLE，构建可能失败，请查看上方日志" >&2
    exit 1
fi

# ---- codesign ----
# QtWebEngine 在 macOS hardened runtime（--options runtime）下需要 JIT 相关授权，
# 否则应用启动后 WebEngine 渲染进程无法启动（白屏 / 崩溃）。entitlements.plist 声明：
#   allow-jit / allow-unsigned-executable-memory / disable-library-validation
ENTITLEMENTS="${ROOT}/macos/entitlements.plist"
CERT_ID="${MACOS_CERT_ID:-}"
if [ -n "$CERT_ID" ]; then
    _sign_id="$CERT_ID"
    _sign_opts=(--options runtime --timestamp)
else
    _sign_id="-"            # ad-hoc：本地可运行，分发需真证书 + 公证
    _sign_opts=()
fi

# 先签署嵌套的 QtWebEngineProcess 助手（它同样需要 JIT 授权，否则运行时起不来渲染进程）
_QT_HELPER="$APP_BUNDLE/Contents/Frameworks/QtWebEngineCore.framework/Helpers/QtWebEngineProcess.app"
if [ -d "$_QT_HELPER" ]; then
    echo "==> [mac] 签署嵌套 QtWebEngineProcess 助手"
    codesign --force "${_sign_opts[@]}" --entitlements "$ENTITLEMENTS" --sign "$_sign_id" "$_QT_HELPER"
fi

echo "==> [mac] 签署主程序（${CERT_ID:+证书}${CERT_ID:-ad-hoc}）"
codesign --force "${_sign_opts[@]}" --entitlements "$ENTITLEMENTS" --deep --sign "$_sign_id" "$APP_BUNDLE"

# ---- dmg ----
DMG="${INSTALLER_DIR}/${APP_NAME}-macOS.dmg"
echo "==> [mac] 生成 dmg：$DMG"
# 用临时挂载目录放置 .app + 应用程序快捷方式，体验更接近官方 dmg
STAGING="$(mktemp -d)"
cp -R "$APP_BUNDLE" "$STAGING/"
ln -s /Applications "$STAGING/Applications"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGING" -ov -format UDZO "$DMG"
rm -rf "$STAGING"

# ---- 公证（可选）----
if [ "${NOTARIZE:-0}" = "1" ]; then
    if [ -z "$CERT_ID" ]; then
        echo "!! NOTARIZE=1 但缺少 MACOS_CERT_ID，无法公证（必须用 Developer ID 证书）" >&2
        exit 1
    fi
    : "${APPLE_ID:?请提供 APPLE_ID（Apple 账号邮箱）}"
    : "${APPLE_TEAM_ID:?请提供 APPLE_TEAM_ID}"
    : "${APPLE_APP_PASSWORD:?请提供 APPLE_APP_PASSWORD（app-specific 密码）}"
    echo "==> [mac] 提交公证：$DMG"
    # 方式一：使用钥匙串中保存的 notarytool 描述文件（推荐，免明文密码）
    #   先：xcrun notarytool store-credentials "mdEditor" --apple-id <id> --team-id <tid> --password <pwd>
    if xcrun notarytool submit "$DMG" \
            --keychain-profile "mdEditor" \
            --wait 2>&1 | tee /tmp/notary.log; then
        echo "==> [mac] 公证通过，staple 票据到 dmg"
        xcrun stapler staple "$DMG"
    else
        # 方式二：用环境变量明文提交（备选）
        echo "==> [mac] 尝试用环境变量明文提交公证"
        xcrun notarytool submit "$DMG" \
            --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" \
            --password "$APPLE_APP_PASSWORD" --wait
        xcrun stapler staple "$DMG"
    fi
else
    echo "==> [mac] 跳过公证（如需 Gatekeeper 免拦截，请用 NOTARIZE=1 重新运行并配置证书/账号）"
fi

echo "==> [mac] 完成。dmg：$DMG"
