#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

CHROMIUM_DIR="$HOME/chromium/src"
WPT_DIR="$HOME/web-platform-tests"

rm -rf out; mkdir out

echo "upstream wpt stats..."
./wpt-stats.sh "$WPT_DIR" > out/wpt-commits.csv
echo

echo "chromium import stats..."
python wpt-import-stats.py "$CHROMIUM_DIR" "$WPT_DIR"
mv import-latencies.csv out/chromium-import-latency.csv
echo

echo "chromium export stats..."
python wpt-export-stats.py "$CHROMIUM_DIR"
mv export-latencies.csv out/chromium-export-latency.csv
echo

echo "chromium usage stats..."
cp wpt-usage-stats "$CHROMIUM_DIR/third_party/WebKit/Tools/Scripts/"
python "$CHROMIUM_DIR/third_party/WebKit/Tools/Scripts/wpt-usage-stats" 2017-12-01 2018-01-01 > out/chromium-usage-stats.txt
echo

echo "chromium OWNERS check..."
./chromium-wpt-owners.sh "$CHROMIUM_DIR/third_party/WebKit/LayoutTests/external/wpt" > out/chromium-wpt-owners.txt
