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

# File name patterns not considered tests
NOT_TEST_PATTERNS = [
    '.*/devtools/',
    '.*/inspector-protocol/',
    # moved in crbug.com/667560
    '.*/inspector/',
    'third_party/WebKit/LayoutTests/FlagExpectations/',
    # TestExpectations, etc.
    'third_party/WebKit/LayoutTests/[^/]*$',
    # WPT_BASE_MANIFEST.json, etc.
    'third_party/WebKit/LayoutTests/external/[^/]*$',
    # lint.whitelist, etc.
    'third_party/WebKit/LayoutTests/external/wpt/[^/]*$',
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
    if not path.startswith('third_party/WebKit/LayoutTests/'):
        return False
    for expr in NOT_TEST_EXPRS:
        if expr.match(path):
            return False
    return True


def is_in_wpt(path):
    return path.startswith('third_party/WebKit/LayoutTests/external/wpt/')


def main():
    host = Host()
    chromium_dir = absolute_chromium_dir(host)

    since = sys.argv[1]
    until = sys.argv[2]

    lt_revs = host.executive.run_command([
        'git', 'rev-list', 'origin/master',
        '--since={}T00:00:00Z'.format(since),
        '--until={}T00:00:00Z'.format(until),
        '--', 'third_party/WebKit/LayoutTests',
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

        author = host.executive.run_command([
            'git', 'show', '-s', '--format=%ae', sha,
        ], cwd=chromium_dir).strip()

        print 'Author:', author
        changes += 1

        if any((is_in_wpt(f) for f in test_files)):
            print 'WPT-Author:', author
            wpt_changes += 1
        else:
            print 'No-WPT-Author:', author

        print 'commit', sha
        for f in changed_files:
            print f
        print

    print '{} source+test changes, {} in wpt'.format(changes, wpt_changes)


if __name__ == '__main__':
    main()
