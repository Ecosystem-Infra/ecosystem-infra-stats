# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

import argparse
import datetime
import os
import re
import sys

from csv_database import ChromiumWPTUsageDB

# Note: Rename to LayoutTests/external/ was on 2017-01-17, in commit
# 6506b8b80db745936336bb88855cd078c083691e.
# The directory was further moved to blink/web_tests/external on
# 2018-11-25 in commit 77578ccb4082ae20a9326d9e673225f1189ebb63.

# File name patterns not considered tests
NOT_TEST_PATTERNS = [
    '.*/devtools/',
    '.*/inspector-protocol/',
    # moved in crbug.com/667560
    '.*/inspector/',
    # Expectations
    'third_party/blink/web_tests/FlagExpectations/',
    # TestExpectations, etc.
    'third_party/blink/web_tests/[^/]*$',
    # WPT_BASE_MANIFEST.json, etc.
    'third_party/blink/web_tests/external/[^/]*$',
    # lint.ignore, etc.
    'third_party/blink/web_tests/external/wpt/[^/]*$',
    # Baselines
    'third_party/blink/web_tests/flag-specific/',
    'third_party/blink/web_tests/platform/',
    'third_party/blink/web_tests/virtual/',
    '.*-expected\\.(txt|png|wav)$',
    # Misc
    '.*/OWNERS$',
    '.*/README(\\.md|\\.txt)?$',
]


NOT_TEST_EXPRS = [re.compile(p) for p in NOT_TEST_PATTERNS]


# Source moved around in the Great Blink mv, https://crbug.com/768828.
SOURCE_PATHS = [
    'third_party/blink/renderer/',
    'third_party/WebKit/Source/',
]


def is_source(path):
    return any(path.startswith(prefix) for prefix in SOURCE_PATHS)


def is_test(path):
    if not path.startswith('third_party/blink/web_tests/'):
        return False
    for expr in NOT_TEST_EXPRS:
        if expr.match(path):
            return False
    return True


def is_in_wpt(path):
    return path.startswith('third_party/blink/web_tests/external/wpt/')


def get_stats(host, chromium_dir, since, until):
    lt_revs = host.executive.run_command([
        'git', 'rev-list', 'origin/master',
        '--since={}-01T00:00:00Z'.format(since),
        '--until={}-01T00:00:00Z'.format(until),
        '--', 'third_party/blink/web_tests',
    ], cwd=chromium_dir).strip().split()

    changes = 0
    wpt_changes = 0
    for sha in lt_revs:
        changed_files = host.executive.run_command([
            'git', 'diff-tree', '--name-only', '--no-commit-id', '-r', sha
        ], cwd=chromium_dir).splitlines()

        # ignore commits that do not touch the source
        if not any((is_source(f) for f in changed_files)):
            continue

        test_files = [f for f in changed_files if is_test(f)]

        if len(test_files) == 0:
            continue

        wpt_change = any((is_in_wpt(f) for f in test_files))
        changes += 1
        if wpt_change:
            wpt_changes += 1
        print(sha, 'WPT' if wpt_change else 'No-WPT')

    print()
    print('{} source+test changes, {} in wpt'.format(changes, wpt_changes))
    fraction = 0 if changes == 0 else wpt_changes / float(changes)
    return {'date': since, 'total_changes': changes, 'changes_with_wpt': wpt_changes, 'fraction': fraction}


def get_next_month(date):
    # Naive implementation; assumes an input of YYYY-MM.
    year, month = [int(x) for x in date.split('-')]
    day = 1
    month += 1
    if month > 12:
        month = 1
        year += 1
    return datetime.date(year, month, day).strftime('%Y-%m')


def date_is_before(a, b):
    # Naive implementation; assumes both a and b are dates in the form YYYY-MM.
    return datetime.datetime.strptime(a, '%Y-%m') < datetime.datetime.strptime(b, '%Y-%m')


def main():
    parser = argparse.ArgumentParser(description='Get stats on WPT usage in Chromium')
    parser.add_argument('chromium_src', help='Path to the src/ folder of a Chromium checkout')
    parser.add_argument('--csv-file', default='wpt-usage.csv', help='CSV file for results; also used to load existing results')
    parser.add_argument('--since', default='2019-01', help='Month to start at (inclusive)')
    parser.add_argument('--until', default=datetime.datetime.now().strftime('%Y-%m'), help='Month to end at (exclusive)')
    args = parser.parse_args()

    # We depend on the blinkpy library, so temporarily modify sys.path to bring
    # it in.
    blink_tools = os.path.join(args.chromium_src, 'third_party', 'blink', 'tools')
    sys.path.insert(0, blink_tools)
    from blinkpy.common.host import Host
    from blinkpy.w3c.chromium_finder import absolute_chromium_dir
    sys.path.remove(blink_tools)

    since = args.since
    until = args.until

    print('Processing WPT usage from', since, 'until', until)

    # Get existing CSV data, if any.
    usage = ChromiumWPTUsageDB(args.csv_file)
    try:
        usage.read()
        since = get_next_month(list(usage.values())[-1]['date'])
        print('Found existing CSV file, processing from', since, 'until', until)
    except (IOError, AssertionError):
        # Non-fatal error
        pass

    if not date_is_before(since, until):
        print('No data to update, finished!')
        return

    host = Host()
    chromium_dir = absolute_chromium_dir(host)

    while date_is_before(since, until):
        print('Getting stats for', since)
        next_month = get_next_month(since)
        usage.add(get_stats(host, chromium_dir, since, next_month))
        since = next_month

    usage.write()


if __name__ == '__main__':
    main()
