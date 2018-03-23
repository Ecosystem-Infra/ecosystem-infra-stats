#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

CHROMIUM_DIR="$HOME/chromium/src"
WPT_DIR="$HOME/web-platform-tests"

# put the output in a directory to match how it will be served:
# https://foolip.github.io/ecosystem-infra-stats/
OUTDIR="out/ecosystem-infra-stats"
rm -rf out
mkdir out

# copy the static webapp content
cp -r webapp "$OUTDIR"

echo "upstream wpt commit stats..."
./wpt-commits.sh "$WPT_DIR" > "$OUTDIR/wpt-commits.csv"
echo

echo "chromium import stats..."
python wpt-import-stats.py "$CHROMIUM_DIR" "$WPT_DIR"
echo

echo "chromium export stats..."
python wpt-export-stats.py "$CHROMIUM_DIR"
echo

mv *.csv "$OUTDIR/"

echo "chromium usage stats..."
cp wpt-usage-stats "$CHROMIUM_DIR/third_party/WebKit/Tools/Scripts/"
python "$CHROMIUM_DIR/third_party/WebKit/Tools/Scripts/wpt-usage-stats" 2018-03-01 2018-04-01 > "$OUTDIR/chromium-usage-stats.txt"
rm "$CHROMIUM_DIR/third_party/WebKit/Tools/Scripts/wpt-usage-stats"
echo

echo "chromium OWNERS check..."
./chromium-wpt-owners.sh "$CHROMIUM_DIR/third_party/WebKit/LayoutTests/external/wpt" > "$OUTDIR/chromium-wpt-owners.txt"
