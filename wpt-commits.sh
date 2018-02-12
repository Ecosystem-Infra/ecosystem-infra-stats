#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

WPT_DIR="$1"
cd "$WPT_DIR"

echo "Month,Total commits,Chromium exports,Gecko exports,Servo exports,WebKit exports"
for month in {2015,2016,2017}-{01,02,03,04,05,06,07,08,09,10,11,12}; do
    # GNU date
    nextmonth=`date +%Y-%m -d "$month-01 +1 month"`
    # BSD date
    #nextmonth=`date -j -f %Y-%m-%d -v+1m "$month-01" +%Y-%m`
    since="$month-01T00:00:00Z"
    until="$nextmonth-01T00:00:00Z"
    commits=`git rev-list origin/master --no-merges --since="$since" --until="$until" --count`
    chromium_exports=`git rev-list origin/master --no-merges --since="$since" --until="$until" --count --grep "^Change-Id:" --grep "^Cr-Commit-Position:"`
    gecko_exports=`git rev-list origin/master --no-merges --since="$since" --until="$until" --count --grep "^Upstreamed from https://bugzilla\\.mozilla\\.org/"`
    servo_exports=`git rev-list origin/master --no-merges --since="$since" --until="$until" --count --grep "^Upstreamed from https://github\\.com/servo/"`
    webkit_exports=`git rev-list origin/master --no-merges --since="$since" --until="$until" --count --grep "^WebKit export of https://bugs\\.webkit\\.org/"`
    echo "$month,$commits,$chromium_exports,$gecko_exports,$servo_exports,$webkit_exports"
done
