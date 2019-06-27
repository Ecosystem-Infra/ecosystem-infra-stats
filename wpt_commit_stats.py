#!/usr/bin/env python3
import abc
import argparse
import logging
import multiprocessing
import os
import pickle
import re
import subprocess
import sys
from datetime import datetime

# For simplicity, we do not want to trace cross the great Blink mv.
BLINK_MOVE = '2018-11-26'
ISO_DATE_FORMAT = '%Y-%m-%d'
# Added, Copied, Modified, Renamed
DIFF_FILTER = 'ACMR'

WEB_TESTS_DIR = 'third_party/blink/web_tests'
WPT_DIR = 'third_party/blink/web_tests/external/wpt'
# File name patterns not considered tests
NOT_TEST_PATTERNS = [
    r'.*/devtools/',
    r'.*/inspector-protocol/',
    # moved in crbug.com/667560
    r'.*/inspector/',
    # expectations
    r'third_party/blink/web_tests/FlagExpectations/',
    # TestExpectations, etc.
    r'third_party/blink/web_tests/[^/]*$',
    # WPT_BASE_MANIFEST.json, etc.
    r'third_party/blink/web_tests/external/[^/]*$',
    # lint.whitelist, etc.
    r'third_party/blink/web_tests/external/wpt/[^/]*$',
    # baselines
    r'third_party/blink/web_tests/flag-specific/',
    r'third_party/blink/web_tests/platform/',
    r'third_party/blink/web_tests/virtual/',
    r'.*-expected\.(txt|png|wav)$',
    # misc
    r'.*/OWNERS$',
    r'.*/README(\.md|\.txt)?$',
]
_NOT_TEST_EXPRS = [re.compile(p) for p in NOT_TEST_PATTERNS]

_log = logging.getLogger('stats')


class Git(object):
    def __init__(self, cwd):
        self.cwd = cwd

    def run(self, *argv):
        args = ('git',) + argv
        _log.debug(' '.join(args))
        return subprocess.check_output(args, cwd=self.cwd, encoding='utf-8')


class AbstractCheck(abc.ABC):
    def __str__(self):
        return '<%s> %s' % (type(self).__name__, self.get_stats())

    # map
    @staticmethod
    @abc.abstractmethod
    def check_revision(git, rev):
        return object  # local result

    # reduce
    @abc.abstractmethod
    def accumulate_result(self, rev, result):
        pass

    @abc.abstractmethod
    def get_result(self):
        return object  # accumulated result

    @abc.abstractmethod
    def get_stats(self):
        return object  # accumulated stats


class CommitStats(AbstractCheck):
    NO_TESTS = 'no tests'
    WPT_ONLY = 'WPT only'
    LEGACY_ONLY = 'legacy only'
    MIXED = 'mixed'

    def __init__(self):
        self.commits = []
        self.wpt_only_commits = []
        self.legacy_only_commits = []

    @staticmethod
    def check_revision(git, rev):
        files = git.run('diff-tree', '--diff-filter='+DIFF_FILTER,
                        '--no-commit-id', '--name-only', '-r',
                        rev, WEB_TESTS_DIR)
        uses_wpt = False
        uses_legacy = False
        for f in files.splitlines():
            if any([r.match(f) for r in _NOT_TEST_EXPRS]):
                continue
            if f.startswith(WPT_DIR):
                uses_wpt = True
            else:
                uses_legacy = True
        if not uses_wpt and not uses_legacy:
            return CommitStats.NO_TESTS
        if uses_wpt and not uses_legacy:
            return CommitStats.WPT_ONLY
        if not uses_wpt and uses_legacy:
            return CommitStats.LEGACY_ONLY
        return CommitStats.MIXED

    def accumulate_result(self, rev, result):
        if result == self.NO_TESTS:
            return
        self.commits.append(rev)
        if result == self.WPT_ONLY:
            self.wpt_only_commits.append(rev)
        elif result == self.LEGACY_ONLY:
            self.legacy_only_commits.append(rev)
        else:
            assert result == self.MIXED, 'Unknown result: ' + str(result)

    def get_result(self):
        return self.commits, self.wpt_only_commits, self.legacy_only_commits

    def get_stats(self):
        if len(self.commits) == 0:
            # Avoid division by zero.
            return 'no commits with web tests found'
        return 'total: %d, WPT-only: %d (%.2f), legacy-only: %d (%.2f)' % (
            len(self.commits),
            len(self.wpt_only_commits),
            float(len(self.wpt_only_commits)) / len(self.commits),
            len(self.legacy_only_commits),
            float(len(self.legacy_only_commits)) / len(self.commits),
        )


class FileStats(AbstractCheck):
    @staticmethod
    def _make_dict():
        return {i: set() for i in DIFF_FILTER}

    def __init__(self):
        self.wpt = self._make_dict()
        self.legacy = self._make_dict()

    @staticmethod
    def check_revision(git, rev):
        output = git.run('diff-tree',
                         '--no-commit-id', '--name-status', '-r',
                         '--diff-filter='+DIFF_FILTER,
                         '-C30', '-M', '--find-copies-harder',
                         rev, WEB_TESTS_DIR)
        wpt = FileStats._make_dict()
        legacy = FileStats._make_dict()
        for line in output.splitlines():
            # status, filename OR status, original filename, new filename
            parts = line.split(maxsplit=2)
            # status could be "Cnn" where nn is the ratio.
            status = parts[0][0]
            f = parts[-1]
            if any([r.match(f) for r in _NOT_TEST_EXPRS]):
                continue
            if f.startswith(WPT_DIR):
                wpt[status].add(f)
            else:
                legacy[status].add(f)
        return (wpt, legacy)

    def accumulate_result(self, rev, result):
        wpt, legacy = result
        for key in self.wpt:
            self.wpt[key] |= wpt[key]
        for key in self.legacy:
            self.legacy[key] |= legacy[key]

    def get_result(self):
        return self.wpt, self.legacy

    def get_stats(self):
        wpt_stats = {k: len(v) for k, v in self.wpt.items()}
        legacy_stats = {k: len(v) for k, v in self.legacy.items()}
        return 'wpt: %s, legacy: %s' % (str(wpt_stats), str(legacy_stats))


class HistoryAnalyzer(object):
    def __init__(self, options, *checks):
        self.options = options
        since = datetime.strptime(self.options.since, ISO_DATE_FORMAT)
        blink_move = datetime.strptime(BLINK_MOVE, ISO_DATE_FORMAT)
        if since < blink_move:
            raise ValueError('since cannot be earlier than %s' % BLINK_MOVE)
        if self.options.until:
            until = datetime.strptime(self.options.until, ISO_DATE_FORMAT)
            if until < since:
                raise ValueError('until cannot be earlier than since')
        self.chromium_dir = os.path.expanduser(self.options.chromium_dir)
        self.web_tests_dir = os.path.normpath(os.path.join(
            self.chromium_dir, WEB_TESTS_DIR))
        if not os.path.isdir(self.web_tests_dir):
            raise ValueError('%s is not a valid Chromium checkout' %
                             self.chromium_dir)
        self.git = Git(self.chromium_dir)
        self.checks = checks
        for check in self.checks:
            assert issubclass(type(check), AbstractCheck)

    def run(self):
        revisions = self.get_rev_list()
        total = len(revisions)
        _log.info('Found %d revisions in range', total)
        current = 0
        pool = multiprocessing.Pool()
        for rev, results in pool.imap(self.run_checks, revisions):
            current += 1
            _log.info('Processed %s [%d/%d]', rev, current, total)
            assert len(results) == len(self.checks)
            for i, result in enumerate(results):
                self.checks[i].accumulate_result(rev, result)

        for check in self.checks:
            print(str(check))

        if self.options.pickle:
            with open(self.options.pickle, 'wb') as f:
                pickle.dump(self.checks, f)

    def run_checks(self, rev):
        # This actually runs in seperate processes. Make sure return values can
        # be pickled.
        results = []
        for check in self.checks:
            results.append(check.check_revision(self.git, rev))
        return rev, results

    def get_rev_list(self):
        # Note that we only get the revisions that touch web_tests, excluding
        # WPT imports.
        argv = ['rev-list', 'origin/master',
                '--invert-grep', '--grep=^Import wpt@']
        if self.options.since:
            argv += ['--since', self.options.since]
        if self.options.until:
            argv += ['--until', self.options.until]
        argv += ['--', self.web_tests_dir]
        return self.git.run(*argv).splitlines()


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('--since', default=BLINK_MOVE,
                        help='YYYY-MM-DD (default: %s)' % BLINK_MOVE)
    parser.add_argument('--until', help='YYYY-MM-DD (default: today)')
    parser.add_argument('--chromium-dir', default='~/chromium/src',
                        help='path to the root of Chromium src '
                             '(default: ~/chromium/src)')
    parser.add_argument('--pickle', help='pickle results to this file')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='debug logging')
    options = parser.parse_args(argv[1:])
    if options.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    analyzer = HistoryAnalyzer(options, CommitStats(), FileStats())
    analyzer.run()


if __name__ == '__main__':
    main(sys.argv)
