#!/usr/bin/python2
# Requirements: numpy & dateutil ( sudo apt install python-{numpy,dateutil} )

from __future__ import print_function
from collections import defaultdict, namedtuple
import dateutil.parser
import json
import re
import numpy
import os
import subprocess

# Only commits after this time (UTC) will be processed.
CUTOFF = '2017-06-01T00:00:00Z'
# Please change this to your chromium checkout.
CHROMIUM_DIR = os.path.expanduser('~/chromium/src')
# Please change this to your upstream WPT checkout.
WPT_DIR = os.path.expanduser('~/github/web-platform-tests')
CHROMIUM_WPT_PATH = 'third_party/WebKit/LayoutTests/external/wpt'
# Target SLA (in minutes).
SLA = 12*60


Import = namedtuple('Import', 'cr_sha, wpt_sha, date')

def git(args, cwd):
    command = ['git'] + args
    # print('EXEC: {} (CWD: {})'.format(' '.join(command), cwd))
    output = subprocess.check_output(command, cwd=cwd)
    return output.rstrip()


def chromium_git(args):
    return git(args, cwd=CHROMIUM_DIR)


def wpt_git(args):
    return git(args, cwd=WPT_DIR)


def list_imports():
    output = chromium_git(
        ['log', '--format=%H|%s|%cI',
         '--after', CUTOFF,
         '--author', 'blink-w3c-test-autoroller@chromium.org']
    )
    imports = []
    subject_re = re.compile(r'^import wpt@(.+)$', re.IGNORECASE)
    for line in output.split('\n'):
        cr_sha, subject, date = line.split('|')
        match = subject_re.match(subject)
        if not match:
            continue
        wpt_sha = match.groups()[0]
        imports.append(Import(cr_sha, wpt_sha, date))
    return imports


def list_wpt_commits(sha1, sha2):
    output = wpt_git(
        ['log', '--format=%H|%cI',
         '{}..{}'.format(sha1, sha2)]
    )
    wpt_commits = []
    if not output:
        return wpt_commits

    for line in output.split('\n'):
        wpt_commits.append(tuple(line.split('|')))
    return wpt_commits


def get_affected_dirs(cr_sha):
    output = chromium_git(['show', '-s', '--format=%b', cr_sha])
    tail = output[output.find('Directory owners for changes in this CL:'):]
    dirs = []
    dir_re = re.compile(r'^  external/wpt/(.+)$')
    for line in tail.split('\n'):
        match = dir_re.match(line)
        if not match:
            continue
        dirs.append(match.groups()[0])
    return dirs


def contains_imported_changes(wpt_sha):
    output = wpt_git(['diff', '--name-only', '--no-renames', wpt_sha])
    for line in output.split('\n'):
        # FIXME: Instead of checking whether the file exists in current
        # Chromium revision, we should check if it is in the import CL.
        filename = os.path.join(CHROMIUM_DIR, CHROMIUM_WPT_PATH, line.strip())
        if os.path.exists(filename):
            return True
    return False


def get_latencies(imports):
    latency_by_month = defaultdict(list)
    previous = None
    current = None
    for step, i in enumerate(imports):
        # Note the commits are ordered reverse chronologically,
        # i.e. the iteration goes back in time.
        current = previous
        previous = i
        if not current:
            continue

        print("{}/{} import {}".format(step, len(imports)-1, current.cr_sha))
        import_time = dateutil.parser.parse(current.date)
        import_month = import_time.strftime('%Y-%m')
        # affected_dirs = get_affected_dirs(current.cr_sha)
        wpt_commits = list_wpt_commits(previous.wpt_sha, current.wpt_sha)
        for wpt_sha, wpt_date in wpt_commits:
            if not contains_imported_changes(wpt_sha):
                print("SKIPPING WPT commit", wpt_sha)
                continue

            wpt_commit_time = dateutil.parser.parse(wpt_date)
            delay = (import_time - wpt_commit_time).total_seconds() / 60
            print("WPT {} latency={}".format(wpt_sha, delay))
            latency_by_month[import_month].append(delay)

    print(latency_by_month)
    return latency_by_month


def analyze_latency(latency_by_month):
    print("Month, Average, 50th percentile, 90th percentile, % meeting SLA")
    for month in sorted(latency_by_month.keys()):
        narr = numpy.asarray(latency_by_month[month])
        print("{}, {}, {}, {}, {}".format(
            month, numpy.average(narr), numpy.percentile(narr, 50),
            numpy.percentile(narr, 90), (narr < SLA).sum() / float(len(narr))
        ))

def main():
    print("Chromium", chromium_git(['rev-parse', 'HEAD']))
    print("WPT", wpt_git(['rev-parse', 'HEAD']))
    imports = list_imports()
    latency_by_month = get_latencies(imports)
    with open('latency.json', 'w') as f:
        json.dump(latency_by_month, f)
    # with open('latency.json') as f:
    #     latency_by_month = json.load(f)
    analyze_latency(latency_by_month)


if __name__ == '__main__':
    main()
