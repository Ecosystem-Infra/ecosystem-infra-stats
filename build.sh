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

# venv setup
if [[ ! -f "env/bin/activate" ]]; then
    python3 -m venv env
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
git checkout origin/gh-pages -- wpt-usage.csv || true
git reset HEAD *.csv || true
echo

echo "upstream wpt commit stats..."
python wpt-commits.py "$WPT_DIR"
echo

echo "chromium usage stats..."
python wpt_usage_stats.py "$CHROMIUM_DIR"
echo

mv *.csv "$OUTDIR/"
