#!/usr/bin/env bash
# =============================================================================
# mdEditor Linux 构建与分发脚本（v3.47，P0 跨平台）
# -----------------------------------------------------------------------------
# 职责：
#   1. 创建 / 复用 Python venv，安装 requirements.txt（PySide6 / PyInstaller / ...）
#   2. 调用 build.py 用 PyInstaller 产出 onedir 的 dist/mdEditor/
#   3. 组装 AppDir 并生成 AppImage（appimagetool，自动下载若缺失）
#   4. （可选）生成 .deb 包（dpkg-deb）
#
# 使用：
#   ./build_linux.sh                 # 构建 + AppImage
#   ./build_linux.sh --deb           # 构建 + AppImage + .deb
#
# 系统依赖（Debian/Ubuntu 例）：
#   sudo apt-get install -y python3-venv python3-pip build-essential \
#       libgl1 libglib2.0-0 libxkbcommon0 libdbus-1-3 libfontconfig1 \
#       fuse  # AppImage 运行时（或 fuse3 / 直接 ./xxx.AppImage）
#   QtWebEngine 还需要若干 lib（libnss3、libxcomposite、libxrandr 等），
#   若启动报缺少 .so，按提示 apt-get install 即可。
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON_BIN="${PYTHON_BIN:-python3}"
APP_NAME="mdEditor"
VENV="${ROOT}/.venv"
INSTALLER_DIR="${ROOT}/installer"
mkdir -p "$INSTALLER_DIR"
DO_DEB=0
for a in "$@"; do [ "$a" = "--deb" ] && DO_DEB=1; done

echo "==> [linux] 准备 venv"
if [ ! -x "${VENV}/bin/python" ]; then
    "$PYTHON_BIN" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "${VENV}/bin/activate"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "==> [linux] PyInstaller 构建 onedir"
python build.py

APP_DIR="${ROOT}/dist/${APP_NAME}"
if [ ! -f "${APP_DIR}/${APP_NAME}" ]; then
    echo "!! 未找到 ${APP_DIR}/${APP_NAME}，构建可能失败" >&2
    exit 1
fi

# ---- 应用图标（可选：用 ImageMagick 把 .ico 转 png；缺失则跳过）----
ICON_PNG="${APP_DIR}/${APP_NAME}.png"
if [ ! -f "$ICON_PNG" ] && command -v convert >/dev/null 2>&1; then
    convert "${ROOT}/src/mdeditor.ico" "$ICON_PNG" 2>/dev/null || true
fi

# ---- AppRun / .desktop ----
cat > "${APP_DIR}/AppRun" <<'EOF'
#!/bin/bash
HERE="$(dirname "$(readlink -f "${0}")")"
exec "${HERE}/${APP_NAME}" "$@"
EOF
chmod +x "${APP_DIR}/AppRun"

cat > "${APP_DIR}/${APP_NAME}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Exec=${APP_NAME}
Icon=${APP_NAME}
Comment=Typora 风格所见即所得 Markdown 编辑器
Categories=Office;Utility;TextEditor;
Terminal=false
EOF

# ---- AppImage ----
ARCH="$(uname -m)"
case "$ARCH" in
    x86_64) AITOOL_ARCH="x86_64" ;;
    aarch64|arm64) AITOOL_ARCH="aarch64" ;;
    *) AITOOL_ARCH="x86_64" ;;
esac
APPIMAGETOOL="${ROOT}/.cache/appimagetool-${AITOOL_ARCH}.AppImage"
if [ ! -x "$APPIMAGETOOL" ]; then
    mkdir -p "${ROOT}/.cache"
    echo "==> [linux] 下载 appimagetool (${AITOOL_ARCH})"
    curl -fL "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${AITOOL_ARCH}.AppImage" \
        -o "$APPIMAGETOOL"
    chmod +x "$APPIMAGETOOL"
fi
# appimagetool 需要 fuse 才能自解压；无 fuse 时加 --appimage-extract 兜底由下方处理
APPIMAGE="${INSTALLER_DIR}/${APP_NAME}-Linux-${AITOOL_ARCH}.AppImage"
echo "==> [linux] 生成 AppImage：$APPIMAGE"
if "$APPIMAGETOOL" --no-appstream "${APP_DIR}" "$APPIMAGE" 2>/dev/null; then
    :
else
    echo "    appimagetool 直接运行失败，尝试 --appimage-extract 方式"
    TMP_AI="$(mktemp -d)"
    ( cd "$TMP_AI" && "$APPIMAGETOOL" --appimage-extract >/dev/null 2>&1 )
    PYTHONWARNINGS=ignore "$TMP_AI/squashfs-root/AppRun" --no-appstream "${APP_DIR}" "$APPIMAGE"
    rm -rf "$TMP_AI"
fi
chmod +x "$APPIMAGE" 2>/dev/null || true
echo "==> [linux] AppImage 完成：$APPIMAGE"

# ---- .deb（可选）----
if [ "$DO_DEB" = "1" ]; then
    echo "==> [linux] 生成 .deb"
    DEB_ROOT="${ROOT}/.deb_staging"
    rm -rf "$DEB_ROOT"
    OPT_DIR="${DEB_ROOT}/opt/${APP_NAME}"
    mkdir -p "${OPT_DIR}" "${DEB_ROOT}/usr/bin" \
             "${DEB_ROOT}/usr/share/applications" \
             "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps" \
             "${DEB_ROOT}/DEBIAN"
    cp -R "${APP_DIR}/." "${OPT_DIR}/"

    cat > "${DEB_ROOT}/usr/bin/${APP_NAME}" <<EOF
#!/bin/bash
exec /opt/${APP_NAME}/${APP_NAME} "\$@"
EOF
    chmod +x "${DEB_ROOT}/usr/bin/${APP_NAME}"

    cp "${APP_DIR}/${APP_NAME}.desktop" "${DEB_ROOT}/usr/share/applications/${APP_NAME}.desktop"
    [ -f "$ICON_PNG" ] && cp "$ICON_PNG" "${DEB_ROOT}/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"

    DEB_ARCH="$AITOOL_ARCH"
    [ "$DEB_ARCH" = "aarch64" ] && DEB_ARCH="arm64"
    # 读取版本号（与 src/config.py APP_VERSION 同步）
    VERSION="$(grep -oP 'APP_VERSION\s*=\s*"\K[^"]+' "${ROOT}/src/config.py" | head -n1)"
    VERSION="${VERSION:-0.0.0}"
    cat > "${DEB_ROOT}/DEBIAN/control" <<EOF
Package: ${APP_NAME,,}
Version: ${VERSION}
Section: office
Priority: optional
Architecture: ${DEB_ARCH}
Depends: libgl1, libglib2.0-0, libxkbcommon0, libdbus-1-3, libfontconfig1, libnss3, libxcomposite1, libxrandr2, libatk1.0-0, libatk-bridge2.0-0, libcups2, libxdamage1, libxshmfence1
Maintainer: WorkBuddy <support@workbuddy.cn>
Description: mdEditor — Typora 风格所见即所得 Markdown 编辑器
 多文档标签、块级所见即所得、KaTeX 公式、Mermaid 图表、六套主题、
 导出 HTML/PDF/Word，支持书籍与双链。
EOF
    DEB="${INSTALLER_DIR}/${APP_NAME,,}-${VERSION}-${DEB_ARCH}.deb"
    dpkg-deb --build --root-owner-group "$DEB_ROOT" "$DEB"
    echo "==> [linux] .deb 完成：$DEB"
fi

echo "==> [linux] 完成。产物目录：${INSTALLER_DIR}"
