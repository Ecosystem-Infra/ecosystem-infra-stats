#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

CHROMIUM_DIR="$HOME/chromium/src"
WPT_DIR="$HOME/web-platform-tests/wpt"

# put the output in a directory to match how it will be served:
# https://ecosystem-infra.github.io/ecosystem-infra-stats/
OUTDIR="out/ecosystem-infra-stats"
rm -rf out
mkdir out

# copy the static webapp content
cp -r webapp "$OUTDIR"

# virtualenv initialization
if [[ ! -f "env/bin/activate" ]]; then
    virtualenv -p python2 --no-site-packages env
fi
set +u
source env/bin/activate
set -u
pip install -U -r requirements.txt
echo

echo "checking out existing CSV files from gh-pages..."
# This is to do incremental updates which is faster. Failure here are harmless.
git fetch origin || true
# Don't combine them into one line in case some file doesn't exist.
git checkout origin/gh-pages -- export-latencies.csv || true
git checkout origin/gh-pages -- wpt-usage.csv || true
git reset HEAD *.csv || true
echo

echo "fetching wpt PRs..."
# note: the first argument isn't used, only passed
python wpt-prs.py "$CHROMIUM_DIR" "$WPT_DIR"
echo

echo "chromium import stats..."
python wpt-import-stats.py "$CHROMIUM_DIR" "$WPT_DIR"
echo

echo "chromium export stats..."
python wpt-export-stats.py "$CHROMIUM_DIR"
echo

echo "wpt.fyi stats..."
# note: the first argument isn't used, only passed
python wpt-dashboard-stats.py "$CHROMIUM_DIR" "$WPT_DIR"
echo

echo "upstream wpt commit stats..."
# note: the first argument isn't used, only passed
python wpt-commits.py "$CHROMIUM_DIR" "$WPT_DIR"
echo

echo "chromium usage stats..."
./wpt_usage_stats.py "$CHROMIUM_DIR"
echo

mv *.csv "$OUTDIR/"

echo "chromium OWNERS check..."
./chromium-wpt-owners.sh "$CHROMIUM_DIR/third_party/blink/web_tests/external/wpt" > "$OUTDIR/chromium-wpt-owners.txt"
