#!/usr/bin/env bash
# 打包自包含工具包 camoufox-reverse-browser/（reverse.9）。
#
# 工具包 = 浏览器二进制 + 离线 addons + Skill + MCP 服务端/客户端 + 说明文档，
# 目标机器拷到 ~/camoufox-reverse-browser 后按包内 README.md / MCP.md 安装即可，
# 不需要 clone 仓库，也不需要访问 GitHub。
#
# 用法：bash scripts/package-toolkit.sh [输出目录]
# 输出目录默认 <repo>/dist-toolkit-reverse.9（gitignored），内含：
#   camoufox-reverse-browser/                 工具包目录
#   camoufox-reverse-browser-reverse.9.tar.gz 同内容的压缩包（解压即得上述目录）
#
# 浏览器 zip 优先复用 dist-release-v152.0.4-beta.30-reverse.9/ 里已打好的
# （SHA-256 一致才复用），否则从本机 camoufox 缓存重新打包。

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="152.0.4"
RELEASE="beta.30"
REVERSE_RELEASE="reverse.9"
SELECTOR_DIR="${VERSION}-${RELEASE}-${REVERSE_RELEASE}"
INSTALL_BASE="${CAMOUFOX_CACHE:-$HOME/Library/Caches/camoufox}"
SRC="$INSTALL_BASE/browsers/whitenightshadow/$SELECTOR_DIR"
ADDONS_SRC="$INSTALL_BASE/addons"
OUT="${1:-$ROOT/dist-toolkit-${REVERSE_RELEASE}}"
TOOLKIT="camoufox-reverse-browser"
ASSET="camoufox-${VERSION}-${RELEASE}-mac.arm64.zip"
RELEASE_DIR="$ROOT/dist-release-v${VERSION}-${RELEASE}-${REVERSE_RELEASE}"

[[ -d "$SRC/Camoufox.app" ]] || { echo "本地未安装 $SELECTOR_DIR 构建: $SRC" >&2; exit 1; }
[[ -f "$SRC/version.json" && -f "$SRC/camoufox-reverse-capabilities.json" ]] || {
    echo "安装目录缺 version.json/capabilities: $SRC" >&2; exit 1; }

PKG="$OUT/$TOOLKIT"
rm -rf "$OUT"
mkdir -p "$PKG/browser" "$PKG/skill" "$PKG/integrations" "$PKG/scripts"

echo "== 浏览器资产"
if [[ -f "$RELEASE_DIR/$ASSET" && -f "$RELEASE_DIR/SHA256SUMS" ]] \
  && ( cd "$RELEASE_DIR" && shasum -a 256 -c SHA256SUMS >/dev/null 2>&1 ); then
  echo "复用 $RELEASE_DIR/$ASSET（SHA-256 已复核）"
  cp "$RELEASE_DIR/$ASSET" "$PKG/browser/$ASSET"
else
  echo "从本机缓存打包 $SRC（zip，需要几分钟）"
  ( cd "$SRC" && zip -qry "$PKG/browser/$ASSET" Camoufox.app version.json \
      camoufox-reverse-capabilities.json )
fi
( cd "$PKG/browser" && shasum -a 256 "$ASSET" > SHA256SUMS )
# 防止接收方 Agent 误以为 zip 是已装好的浏览器、或在本目录找 install.sh
cat > "$PKG/browser/INSTALL.txt" <<EOF
本目录的 zip 是【待安装资产】，不是已安装的浏览器。
安装命令（在工具包根目录执行，详见根目录 README.md）：

  python3 scripts/install-camoufox-reverse.py \\
    browser/$ASSET \\
    --sha256 "\$(awk '/$ASSET\$/ {print \$1}' browser/SHA256SUMS)"

本目录没有 install.sh，请不要寻找或创建它。
EOF

echo "== 离线 addons（已提取的默认组件，存在才带）"
if [[ -d "$ADDONS_SRC" ]]; then
  mkdir -p "$PKG/browser/addons"
  for addon in "$ADDONS_SRC"/*/; do
    [[ -f "$addon/manifest.json" ]] || continue
    cp -R "$addon" "$PKG/browser/addons/$(basename "$addon")"
    echo "  携带组件：$(basename "$addon")"
  done
fi

echo "== Skill / MCP / 文档"
mkdir -p "$PKG/skill/camoufox-reverse-browser"
cp -R skill/ "$PKG/skill/camoufox-reverse-browser/"
cp -R pythonlib "$PKG/pythonlib"
cp -R mcp "$PKG/mcp"
cp -R integrations/camoufox-reverse-mcp "$PKG/integrations/camoufox-reverse-mcp"
cp scripts/install-camoufox-reverse.py scripts/run-reverse-mcp.sh \
   scripts/reverse-browser-instrumentation-divergence.py scripts/mcp-cleanup.sh \
   scripts/crb.py "$PKG/scripts/"
chmod +x "$PKG/scripts/run-reverse-mcp.sh" "$PKG/scripts/mcp-cleanup.sh" "$PKG/scripts/crb.py"
cp scripts/release/toolkit/README.md "$PKG/README.md"
cp scripts/release/toolkit/MCP.md "$PKG/MCP.md"

# 清掉缓存/元数据垃圾
find "$PKG" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$PKG" \( -name '*.egg-info' -o -name '.DS_Store' \) -prune -exec rm -rf {} +

echo "== 压缩包"
( cd "$OUT" && tar -czf "camoufox-reverse-browser-${REVERSE_RELEASE}.tar.gz" "$TOOLKIT" )

echo "== 校验浏览器资产"
/usr/local/bin/python3.12 scripts/validate_reverse_build.py --archive "$PKG/browser/$ASSET"

echo
echo "完成：$PKG"
echo "压缩包：$OUT/camoufox-reverse-browser-${REVERSE_RELEASE}.tar.gz"
du -sh "$PKG" "$OUT/camoufox-reverse-browser-${REVERSE_RELEASE}.tar.gz"
