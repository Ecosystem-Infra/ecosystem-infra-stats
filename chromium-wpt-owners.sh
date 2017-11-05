#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

CHROMIUM_DIR="$1"
cd "$CHROMIUM_DIR/src/third_party/WebKit/LayoutTests/external/wpt"

(
    find * -maxdepth 0 -type d;
    find css/* -maxdepth 0 -type d
) | grep -vE '^(common|css|css/fonts|css/reference|css/support|css/vendor-imports|fonts|interfaces|media)$' | while read d; do
    if [[ ! -f "$d/OWNERS" ]]; then
        echo "Missing OWNERS: $d"
        continue
    fi
    if [[ -z "$(find $d -type f ! -name OWNERS)" ]]; then
        echo "Orphaned OWNERS: $d"
        continue
    fi
    grep -qF 'file://' "$d/OWNERS" && continue
    grep -qF '# TEAM: ' "$d/OWNERS" || echo "Missing TEAM: $d"
    grep -qF '# COMPONENT: ' "$d/OWNERS" || echo "Missing COMPONENT: $d"
done
