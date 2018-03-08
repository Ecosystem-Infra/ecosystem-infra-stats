#!/usr/bin/env python
# History: https://gist.github.com/jeffcarp/f1fb015e38f50e82d30b8c69b67faa74
#          https://gist.github.com/Hexcles/ec811c9dd45a0f21bb3fc3243bfa857a
# Requirements: python-dateutil, numpy & requests

from __future__ import print_function
from collections import defaultdict
import csv

import dateutil.parser
import numpy

from csv_database import ExportLatencyDB, ExportLatencyStatDB
from wpt_common import CUTOFF, QUARTER_START, chromium_git, fetch_all_prs, is_export_pr


# Target SLA (in minutes).
SLA = 60
# Result files.
LATENCIES_CSV = 'export-latencies.csv'
STATS_CSV = 'export-latency-stats.csv'

_GITHUB_DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


def get_sha_from_change_id(change_id):
    grep = '^Change-Id: ' + change_id + '$'
    args = ['log', 'origin/master', '--format=%H', '-1', '--grep=%s' % grep]
    sha = chromium_git(args)
    if len(sha) == 40:
        return sha
    else:
        return None


def get_sha_from_commit_position(commit_position):
    args = ['crrev-parse', commit_position]
    sha = chromium_git(args)
    if len(sha) == 40:
        return sha
    else:
        return None


def get_latencies(prs):
    try:
        latencies = ExportLatencyDB(LATENCIES_CSV)
        latencies.read()
        print('Read', len(latencies), 'latency entries from', LATENCIES_CSV)
        print('Processing new PRs')
    except (IOError, AssertionError):
        latencies = ExportLatencyDB(LATENCIES_CSV)

    skipped = []
    total_prs = len(prs)
    for index, pr in enumerate(prs):
        pr_number = pr['PR']
        print('[{}/{}] PR: https://github.com/w3c/web-platform-tests/pull/{}'
              .format(index + 1, total_prs, pr_number))
        if latencies.get(pr_number):
            continue

        merged_at = dateutil.parser.parse(pr['merged_at'])
        chromium_commit = pr['chromium_commit']
        if chromium_commit.startswith('I'):
            sha = get_sha_from_change_id(chromium_commit)
        else:
            sha = get_sha_from_commit_position(chromium_commit)

        if sha is None:
            print('Unable to find commit. SKIPPING!')
            skipped.append(pr_number)
            continue

        commit_time_str = chromium_git(['show', '-s', '--format=%cI', sha]).strip()
        commit_time = dateutil.parser.parse(commit_time_str)
        delay = (merged_at - commit_time).total_seconds() / 60

        print('Found Chromium commit {} committed at {}'.format(sha, commit_time_str))
        print('Export PR merged at {}'.format(merged_at))
        print('Delay (mins):', delay)
        if delay < 0:
            print('Negative delay. SKIPPING!')
            skipped.append(pr_number)
            continue
        latencies.add({
            'PR': pr_number,
            'exported_sha': sha,
            'commit_time': commit_time_str,
            'latency': delay,
        })

    if skipped:
        print('Skipped PRs:', skipped)

    print('Writing file', LATENCIES_CSV)
    latencies.write()
    return latencies


def analyze(latencies):
    latency_by_week = defaultdict(list)
    this_quarter = []
    quarter_cutoff = dateutil.parser.parse(QUARTER_START)
    for datapoint in latencies.values():
        commit_time = dateutil.parser.parse(datapoint['commit_time'])
        commit_week = commit_time.strftime('%Y-%UW')
        latency = float(datapoint['latency'])
        latency_by_week[commit_week].append(latency)
        if commit_time >= quarter_cutoff:
            this_quarter.append(latency)

    print('NOTE: Results eariler than cutoff time ({}) are not accurate.'
          .format(CUTOFF))

    stats = ExportLatencyStatDB(STATS_CSV)
    for week, values in latency_by_week.iteritems():
        narr = numpy.asarray(values)
        stats.add({
            'Week': week,
            'PRs': len(narr),
            '50%': numpy.percentile(narr, 50),
            '90%': numpy.percentile(narr, 90),
            'Mean': numpy.average(narr),
            'Meeting SLA': (narr < SLA).sum() / float(len(narr)),
        })
    stats.write(order='asc')

    quarter_total = len(this_quarter)
    np_this_quarter = numpy.asarray(this_quarter)
    out_of_sla = (np_this_quarter > SLA).sum()
    print('This quarter since', QUARTER_START, '(Chromium commit time):')
    print('Average latency (mins):', numpy.average(np_this_quarter))
    print('Quarter 50th percentile (mins):', numpy.percentile(np_this_quarter, 50))
    print('Quarter 90th percentile (mins):', numpy.percentile(np_this_quarter, 90))
    print('{} / {} PRs out of {} min SLA ({})'.format(
        out_of_sla, quarter_total, SLA, out_of_sla / float(quarter_total)))
    print('KR:', (quarter_total - out_of_sla) / float(quarter_total))


def main():
    pr_db = fetch_all_prs()
    export_prs = [pr for pr in pr_db.values() if is_export_pr(pr)]
    latencies = get_latencies(export_prs)
    analyze(latencies)


if __name__ == '__main__':
    main()
