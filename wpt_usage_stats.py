#!/usr/bin/env python2
# Copyright 2017 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

from blinkpy.common.host import Host
from blinkpy.w3c.chromium_finder import absolute_chromium_dir

import re
import sys

# Note: Rename to LayoutTests/external/ was on 2017-01-17, in commit
# 6506b8b80db745936336bb88855cd078c083691e.
# The directory was further moved to blink/web_tests/external on
# 2017-11-25 in commit 77578ccb4082ae20a9326d9e673225f1189ebb63.

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
    # lint.whitelist, etc.
    'third_party/blink/web_tests/external/wpt/[^/]*$',
    # Baselines
    'third_party/blink/web_tests/flag-specific/',
    'third_party/blink/web_tests/platform/',
    'third_party/blink/web_tests/virtual/',
    '.*-expected\.(txt|png|wav)$',
    # Misc
    '.*/OWNERS$',
    '.*/README(\.md|\.txt)?$',
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


def main():
    host = Host()
    chromium_dir = absolute_chromium_dir(host)

    since = sys.argv[1]
    until = sys.argv[2]

    lt_revs = host.executive.run_command([
        'git', 'rev-list', 'origin/master',
        '--since={}T00:00:00Z'.format(since),
        '--until={}T00:00:00Z'.format(until),
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
        print sha, 'WPT' if wpt_change else 'No-WPT'

    print
    print '{} source+test changes, {} in wpt'.format(changes, wpt_changes)


if __name__ == '__main__':
    main()
