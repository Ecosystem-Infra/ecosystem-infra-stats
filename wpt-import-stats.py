#!/usr/bin/env python
# History: https://gist.github.com/Hexcles/ec48b4f674ad66c6d34cf279c262a4de
# Requirements: python-dateutil, numpy

from __future__ import print_function
from collections import defaultdict, namedtuple
import csv
import dateutil.parser
import json
import numpy
import re
import subprocess

from wpt_common import CUTOFF, QUARTER_START, chromium_git, fetch_all_prs, is_export_pr, wpt_git


# Target SLA (in minutes).
SLA = 12*60
# Result files.
MINS_FILE = 'import-mins.json'
CSV_FILE = 'import-latencies.csv'


Import = namedtuple('Import', 'cr_sha, wpt_sha, date')


def list_imports():
    output = chromium_git([
        'log', '--format=%H|%s|%cI',
        '--grep=^[Ii]mport wpt@',
        '--after', CUTOFF,
        '--reverse',  # our binary_search uses chronological order.
        # Uncomment the line below to count only auto imports.
        # '--author', 'blink-w3c-test-autoroller@chromium.org'
    ])
    imports = []
    subject_re = re.compile(r'^[Ii]mport wpt@(\w+)')
    for line in output.split('\n'):
        cr_sha, subject, date = line.split('|')
        match = subject_re.match(subject)
        if not match:
            continue
        wpt_sha = match.groups()[0]
        imports.append(Import(cr_sha, wpt_sha, date))
    return imports


def _compare_commits(sha1, sha2):
    if sha1 == sha2:
        return 0
    try:
        wpt_git(['merge-base', '--is-ancestor', sha1, sha2])
        # SHA1 is an ancestor of SHA2
        return -1
    except subprocess.CalledProcessError:
        # The exception is raised when the return code is non-zero.
        return 1


def binary_search_import(wpt_commit, imports):
    """Finds which import includes the given wpt_commit."""
    left = 0
    right = len(imports) - 1
    while left < right:
        mid = (left + right) // 2
        current = imports[mid]
        comp = _compare_commits(wpt_commit, current.wpt_sha)
        if comp <= 0:
            right = mid
        else:
            left = mid+1
    return left


def get_latencies(imports, prs):
    try:
        with open(MINS_FILE) as f:
            latencies = json.load(f)
            print('Read', len(latencies), 'results from', MINS_FILE)
            return latencies
    except (IOError, ValueError):
        pass

    latencies = {}
    total_prs = len(prs)
    for index, pr in enumerate(prs):
        print("[{}/{}] PR: {}".format(index + 1, total_prs, pr['html_url']))
        merge_commit = pr['merge_commit_sha']
        merged_at = pr['merged_at']
        try:
            wpt_git(['cat-file', '-t', merge_commit])
        except subprocess.CalledProcessError:
            print('Merge commit {} does not exist. SKIPPING!'
                  .format(merge_commit))
            continue
        if _compare_commits(merge_commit, imports[-1].wpt_sha) > 0:
            print('Merge point {} after last import point {}. SKIPPING!'
                  .format(merge_commit, imports[-1].wpt_sha))
            continue
        if _compare_commits(merge_commit, imports[0].wpt_sha) < 0:
            print('Merge point {} before first import point {}. SKIPPING!'
                  .format(merge_commit, imports[0].wpt_sha))
            continue

        index_found = binary_search_import(merge_commit, imports)
        import_found = imports[index_found]
        previous_import = imports[index_found - 1]
        # Check if I get my binary search right :)
        assert _compare_commits(merge_commit, import_found.wpt_sha) <= 0, \
               "PR merge point {} after import {}".format(
                   merge_commit, import_found)
        assert _compare_commits(merge_commit, previous_import.wpt_sha) > 0, \
               "PR merge point {} before the previous import {}".format(
                   merge_commit, previous_import)

        import_time = dateutil.parser.parse(imports[index_found].date)
        wpt_merge_time = dateutil.parser.parse(merged_at)
        delay = (import_time - wpt_merge_time).total_seconds() / 60
        print('PR merged at {} imported at {}'.format(
            merge_commit, import_found.wpt_sha))
        print('Chromium import {} at {}'.format(
            import_found.cr_sha, import_found.date))
        print('Delay (mins):', delay)
        latencies[merge_commit] = {
            'import_sha': import_found.cr_sha,
            'import_time': import_found.date,
            'latency': delay,
        }

    print('Writing file', MINS_FILE)
    with open(MINS_FILE, 'w') as f:
        json.dump(latencies, f, indent=2)

    return latencies


def analyze(latencies):
    latency_by_month = defaultdict(list)
    this_quarter = []
    quarter_cutoff = dateutil.parser.parse(QUARTER_START)
    for datapoint in latencies.values():
        import_time = dateutil.parser.parse(datapoint['import_time'])
        import_month = import_time.strftime('%Y-%m')
        latency_by_month[import_month].append(datapoint['latency'])
        if import_time >= quarter_cutoff:
            this_quarter.append(datapoint['latency'])

    sla_field = '% meeting SLA ({} mins)'.format(SLA)
    with open(CSV_FILE, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=[
            'Month', '50th percentile', '90th percentile', 'Average', 'PRs', sla_field])
        writer.writeheader()
        for month in sorted(latency_by_month.keys()):
            narr = numpy.asarray(latency_by_month[month])
            month_stat = {
                'Month': month,
                '50th percentile': numpy.percentile(narr, 50),
                '90th percentile': numpy.percentile(narr, 90),
                'Average': numpy.average(narr),
                'PRs': len(narr),
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
    print('KR:', (quarter_total - out_of_sla) / float(quarter_total))


def main():
    all_prs = fetch_all_prs()
    non_export_prs = [pr for pr in all_prs if not is_export_pr(pr)]
    imports = list_imports()
    latencies = get_latencies(imports, non_export_prs)
    analyze(latencies)


if __name__ == '__main__':
    main()
