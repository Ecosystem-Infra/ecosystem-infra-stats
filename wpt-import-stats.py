#!/usr/bin/python2
# History: https://gist.github.com/Hexcles/ec48b4f674ad66c6d34cf279c262a4de
# Requirements: numpy & dateutil ( sudo apt install python-{numpy,dateutil} )

from __future__ import print_function
from collections import defaultdict, namedtuple
import csv
import dateutil.parser
import json
import re
import numpy
import os
import subprocess
import sys

# Only PRs after this time (UTC) will be processed.
CUTOFF = '2017-07-01T00:00:00Z'
QUARTER_START = '2017-10-01T00:00:00Z'
try:
    CHROMIUM_DIR = sys.argv[1]
    WPT_DIR = sys.argv[2]
except IndexError:
    CHROMIUM_DIR = os.path.expanduser('~/chromium/src')
    WPT_DIR = os.path.expanduser('~/github/web-platform-tests')
CHROMIUM_WPT_PATH = 'third_party/WebKit/LayoutTests/external/wpt'
# Target SLA (in minutes).
SLA = 12*60
MINS_FILE = 'import-mins.json'
CSV_FILE = 'import-latencies.csv'


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
    output = chromium_git([
        'log', '--format=%H|%s|%cI',
        '--grep=^[Ii]mport wpt@',
        '--after', CUTOFF,
        # Uncomment the line below to count only auto imports.
        # '--author', 'blink-w3c-test-autoroller@chromium.org'
    ])
    imports = []
    subject_re = re.compile(r'^import wpt@(\w+)', re.IGNORECASE)
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
    try:
        with open(MINS_FILE) as f:
            latencies = json.load(f)
            print('Read', len(latencies), 'results from', MINS_FILE)
            return latencies
    except Exception:
        pass

    latencies = {}
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
        # affected_dirs = get_affected_dirs(current.cr_sha)
        wpt_commits = list_wpt_commits(previous.wpt_sha, current.wpt_sha)
        for wpt_sha, wpt_date in wpt_commits:
            if not contains_imported_changes(wpt_sha):
                print("SKIPPING WPT commit", wpt_sha)
                continue

            wpt_commit_time = dateutil.parser.parse(wpt_date)
            delay = (import_time - wpt_commit_time).total_seconds() / 60
            latencies[wpt_sha] = {
                'import_sha': current.cr_sha,
                'import_time': current.date,
                'latency': delay,
            }

    print('Writing file', MINS_FILE)
    with open(MINS_FILE, 'w') as f:
        json.dump(latencies, f)

    return latencies


def analyze(latencies):
    latency_by_month = defaultdict(list)
    this_quarter = []
    quarter_cutoff = dateutil.parser.parse(QUARTER_START)
    for datapoint in latencies.itervalues():
        import_time = dateutil.parser.parse(datapoint['import_time'])
        import_month = import_time.strftime('%Y-%m')
        latency_by_month[import_month].append(datapoint['latency'])
        if import_time >= quarter_cutoff:
            this_quarter.append(datapoint['latency'])
            print("{},{},{}".format(datapoint['import_sha'], datapoint['import_time'], datapoint['latency']))

    sla_field = '% meeting SLA ({} mins)'.format(SLA)
    with open(CSV_FILE, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['Month', 'PRs', '50th percentile', '90th percentile', 'Average', sla_field])
        writer.writeheader()
        for month in sorted(latency_by_month.keys()):
            narr = numpy.asarray(latency_by_month[month])
            month_stat = {
                'Month': month,
                'PRs': len(narr),
                '50th percentile': numpy.percentile(narr, 50),
                '90th percentile': numpy.percentile(narr, 90),
                'Average': numpy.average(narr),
                sla_field: (narr < SLA).sum() / float(len(narr)),
            }
            writer.writerow(month_stat)

    quarter_total = len(this_quarter)
    np_this_quarter = numpy.asarray(this_quarter)
    average = numpy.average(np_this_quarter)
    out_of_sla = (np_this_quarter > SLA).sum()
    print('This quarter since', QUARTER_START, '(PR merge time):')
    print('Average CL committed to PR merged latency:', average, 'minutes')
    print('Quarter 50th percentile', numpy.percentile(np_this_quarter, 50))
    print('Quarter 90th percentile', numpy.percentile(np_this_quarter, 90))
    print('{} / {} PRs out of {} min SLA ({})'.format(
        out_of_sla, quarter_total, SLA, out_of_sla / float(quarter_total)))
    print('KR: in_sla =', (quarter_total - out_of_sla) / float(quarter_total))


def main():
    print("Chromium", chromium_git(['rev-parse', 'HEAD']))
    print("WPT", wpt_git(['rev-parse', 'HEAD']))
    imports = list_imports()
    latencies = get_latencies(imports)
    analyze(latencies)


if __name__ == '__main__':
    main()
