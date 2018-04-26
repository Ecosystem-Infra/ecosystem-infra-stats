#!/usr/bin/env python
# History: https://gist.github.com/Hexcles/ec48b4f674ad66c6d34cf279c262a4de
# Requirements: python-dateutil, numpy

from __future__ import print_function
from collections import defaultdict, namedtuple
import re

import dateutil.parser
import numpy

from csv_database import ImportLatencyDB, ImportLatencyStatDB
from wpt_common import CUTOFF, QUARTER_START, chromium_git, fetch_all_prs, \
    get_pr_latencies, is_export_pr


# Target SLA (in minutes).
SLA = 12*60
# Result files.
LATENCIES_CSV = 'import-latencies.csv'
STATS_CSV = 'import-latency-stats.csv'


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


def get_latencies(imports, prs):
    db = ImportLatencyDB(LATENCIES_CSV)

    latencies = get_pr_latencies(
        prs, events=imports,
        event_sha_func=lambda i: i.wpt_sha,
        event_date_func=lambda i: dateutil.parser.parse(i.date))

    for entry in latencies:
        i = entry['event']
        if i is None:
            continue
        db.add({
            'PR': str(entry['pr']['PR']),
            'import_sha': i.cr_sha,
            'import_time': i.date,
            'latency': entry['latency'],
        })

    print('Writing file', LATENCIES_CSV)
    db.write(order='asc')
    return db


def analyze(latencies):
    latency_by_week = defaultdict(list)
    this_quarter = []
    quarter_cutoff = dateutil.parser.parse(QUARTER_START)
    for datapoint in latencies.values():
        import_time = dateutil.parser.parse(datapoint['import_time'])
        import_week = import_time.strftime('%Y-%UW')
        latency = float(datapoint['latency'])
        latency_by_week[import_week].append(latency)
        if import_time >= quarter_cutoff:
            this_quarter.append(latency)

    stats = ImportLatencyStatDB(STATS_CSV)
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
    print('This quarter since', QUARTER_START, '(import time):')
    print('Average latency (mins):', numpy.average(np_this_quarter))
    print('Quarter 50th percentile (mins):',
          numpy.percentile(np_this_quarter, 50))
    print('Quarter 90th percentile (mins):',
          numpy.percentile(np_this_quarter, 90))
    print('{} / {} PRs out of {} min SLA ({})'.format(
        out_of_sla, quarter_total, SLA, out_of_sla / float(quarter_total)))
    print('KR:', (quarter_total - out_of_sla) / float(quarter_total))


def main():
    # When computing latencies it is important that all PRs are used,
    # including export PRs, as we can import an export PR and bring along
    # other changes since the previous import. https://crrev.com/31261077b
    # is such an import.
    prs = fetch_all_prs().values()
    imports = list_imports()
    latencies = get_latencies(imports, prs)
    analyze(latencies)


if __name__ == '__main__':
    main()
