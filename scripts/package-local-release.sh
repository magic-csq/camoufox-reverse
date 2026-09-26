#!/usr/bin/env bash
# 本地打包 release 产物（等不及 GHA 时使用）。
# 从本机已安装的 reverse.9 构建（~/Library/Caches/camoufox/browsers/...）
# 打出与 GHA release 完全同构的本地产物目录：
#   camoufox-152.0.4-beta.30-mac.arm64.zip（含 version.json + capabilities）
#   SHA256SUMS / BUILD-MANIFEST.json
#   camoufox-reverse-agent-reverse.9.tar.gz（agent 自举包）
#   install-camoufox-reverse.py
#
# 用法：bash scripts/package-local-release.sh [输出目录]
# 输出目录默认 <repo>/dist-release-v152.0.4-beta.30-reverse.9（gitignored）。
# 本地使用：CAMOUFOX_REVERSE_RELEASE_BASE="file://<输出目录>" bash install.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="152.0.4"
RELEASE="beta.30"
REVERSE_RELEASE="reverse.9"
SELECTOR_DIR="${VERSION}-${RELEASE}-${REVERSE_RELEASE}"
INSTALL_BASE="${CAMOUFOX_CACHE:-$HOME/Library/Caches/camoufox}"
SRC="$INSTALL_BASE/browsers/whitenightshadow/$SELECTOR_DIR"
OUT="${1:-$ROOT/dist-release-v${VERSION}-${RELEASE}-${REVERSE_RELEASE}}"
ASSET="camoufox-${VERSION}-${RELEASE}-mac.arm64.zip"
BUNDLE="camoufox-reverse-agent-${REVERSE_RELEASE}.tar.gz"

[[ -d "$SRC/Camoufox.app" ]] || { echo "本地未安装 $SELECTOR_DIR 构建: $SRC" >&2; exit 1; }
[[ -f "$SRC/version.json" && -f "$SRC/camoufox-reverse-capabilities.json" ]] || {
    echo "安装目录缺 version.json/capabilities: $SRC" >&2; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"

echo "== 打包浏览器资产（zip，与 GHA Linux runner 产物同构）"
( cd "$SRC" && zip -qry "$OUT/$ASSET" Camoufox.app version.json \
    camoufox-reverse-capabilities.json )

echo "== 打包 agent 自举包（与 GHA 工作流同款布局）"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
PKG="$STAGE/camoufox-reverse-agent"
mkdir -p "$PKG/scripts" "$PKG/integrations"
cp -R pythonlib "$PKG/pythonlib"
cp -R mcp "$PKG/mcp"
cp -R integrations/camoufox-reverse-mcp "$PKG/integrations/camoufox-reverse-mcp"
cp -R skill "$PKG/skill"
cp scripts/install-camoufox-reverse.py scripts/install_reverse_browser_agent.py \
   scripts/run-reverse-mcp.sh scripts/mcp-cleanup.sh scripts/release_bootstrap.py \
   "$PKG/scripts/"
cp scripts/release/install.sh "$PKG/install.sh"
chmod +x "$PKG/install.sh"
# 清掉缓存/元数据垃圾
find "$PKG" -name '__pycache__' -type d -prune -exec rm -rf {} +
find "$PKG" \( -name '*.egg-info' -o -name '.DS_Store' \) -prune -exec rm -rf {} +
( cd "$STAGE" && tar -czf "$OUT/$BUNDLE" -C "$STAGE" "camoufox-reverse-agent" )

echo "== 生成校验清单与构建清单"
BSHA=$(shasum -a 256 "$OUT/$ASSET" | awk '{print $1}')
BNDSHA=$(shasum -a 256 "$OUT/$BUNDLE" | awk '{print $1}')
{
  echo "$BSHA  $ASSET"
  echo "$BNDSHA  $BUNDLE"
} > "$OUT/SHA256SUMS"
cp scripts/install-camoufox-reverse.py "$OUT/install-camoufox-reverse.py"

/usr/local/bin/python3.12 - "$OUT" "$ASSET" "$BSHA" "$BUNDLE" "$BNDSHA" <<'PY'
import json, sys
from pathlib import Path
out, asset, asha, bundle, bsha = sys.argv[1:6]
cap = json.loads(Path(out, asset.replace(".zip", "") + ".unused").read_text()) if False else None
import zipfile
with zipfile.ZipFile(Path(out) / asset) as z:
    cap = json.loads(z.read("camoufox-reverse-capabilities.json"))
manifest = {
    "schema": 1,
    "upstream_tag": "v" + cap["upstream_version"],
    "reverse_release": cap["reverse_release"],
    "reverse_commit": "local-build",
    "property_trace_protocol": cap["property_trace_protocol"],
    "property_trace_hooks": cap["property_trace_hooks"],
    "property_trace_features": cap["property_trace_features"],
    "assets": [
        {"name": asset, "size": (Path(out) / asset).stat().st_size, "sha256": asha},
        {"name": bundle, "size": (Path(out) / bundle).stat().st_size, "sha256": bsha},
    ],
    "note": "local build via scripts/package-local-release.sh",
}
Path(out, "BUILD-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
PY

echo "== 校验资产"
/usr/local/bin/python3.12 scripts/validate_reverse_build.py --archive "$OUT/$ASSET"

echo
echo "完成：$OUT"
ls -lh "$OUT"
