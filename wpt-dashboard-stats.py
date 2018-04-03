#!/usr/bin/env python
# Requirements: python-dateutil, numpy, requests

from __future__ import print_function
from collections import defaultdict, namedtuple
import csv
import dateutil.parser
import json
import numpy
import re
import requests
import subprocess

from wpt_common import CUTOFF, QUARTER_START, fetch_all_prs, get_pr_latencies, wpt_git

# use a large number to avoid https://github.com/w3c/wptdashboard/issues/524
RUNS_URL='https://wpt.fyi/api/runs?max-count=100'
CSV_FILE = 'wpt-dashboard-latency.csv'


def get_latencies(prs, runs):
    """For each PR, find the earliest run for each browser that included that PR,
    and calucate the latencies between the PR and the runs."""

    # calculate latencies for each browser individually, and for a virtual
    # "all browsers" run, which is limited by the slowest running browser.
    browsers = list(set(run['browser_name'] for run in runs))
    # if the set of browsers changes, this script must adapt
    browsers.sort()
    assert browsers == ['chrome', 'edge', 'firefox', 'safari']

    # get the complete runs by starting with the union of all and intersecting
    # with the runs for each browser.
    complete_shas = set(run['revision'] for run in runs)
    for browser in browsers:
        browser_runs = (run['revision'] for run in runs if run['browser_name'] == browser)
        complete_shas.intersection_update(browser_runs)
    print(len(complete_shas), 'complete runs:')
    for sha in complete_shas:
        complete_runs = [run for run in runs if run['revision'] == sha]
        print(json.dumps(complete_runs, indent=2))
        # https://github.com/w3c/wptdashboard/issues/528
        assert len(complete_runs) == 4, len(complete_runs)
        dates = [run['created_at'] for run in complete_runs]
        print('  ', ' '.join(date))

    # TODO
    for run in runs:
        #print(run['revision'])
        break

    return get_pr_latencies(prs, runs)

def main():
    prs = fetch_all_prs()
    runs = requests.get(RUNS_URL).json()
    latencies = get_latencies(prs, runs)
    print(latencies)


if __name__ == '__main__':
    main()
