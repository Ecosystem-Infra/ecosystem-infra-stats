#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

CHROMIUM_DIR="$HOME/chromium/src"
WPT_DIR="$HOME/web-platform-tests"

rm -rf out; mkdir out
# Check out databases from gh-pages, which may fail harmlessly.
git fetch origin || true
# Don't combine them into one line in case some file doesn't exist.
git checkout origin/gh-pages -- wpt-prs.csv || true
git checkout origin/gh-pages -- import-latencies.csv || true
git checkout origin/gh-pages -- export-latencies.csv || true
git reset HEAD *.csv || true

echo "upstream wpt commit stats..."
./wpt-commits.sh "$WPT_DIR" > out/wpt-commits.csv
echo

echo "chromium import stats..."
python wpt-import-stats.py "$CHROMIUM_DIR" "$WPT_DIR"
echo

echo "chromium export stats..."
python wpt-export-stats.py "$CHROMIUM_DIR"
echo

mv *.csv out/

echo "chromium usage stats..."
cp wpt-usage-stats "$CHROMIUM_DIR/third_party/WebKit/Tools/Scripts/"
python "$CHROMIUM_DIR/third_party/WebKit/Tools/Scripts/wpt-usage-stats" 2018-03-01 2018-04-01 > out/chromium-usage-stats.txt
rm "$CHROMIUM_DIR/third_party/WebKit/Tools/Scripts/wpt-usage-stats"
echo

echo "chromium OWNERS check..."
./chromium-wpt-owners.sh "$CHROMIUM_DIR/third_party/WebKit/LayoutTests/external/wpt" > out/chromium-wpt-owners.txt
