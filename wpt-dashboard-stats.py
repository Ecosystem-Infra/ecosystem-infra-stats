#!/usr/bin/env python

import dateutil.parser
import requests

from csv_database import RunLatencyDB
from wpt_common import fetch_all_prs, get_pr_latencies

# 1000 because of https://github.com/w3c/wptdashboard/issues/524
RUNS_URL='https://wpt.fyi/api/runs?max-count=1000'
CSV_PATH_TEMPLATE = 'wpt-dashboard-{}-latencies.csv'

# If the runs expand to non-desktop platforms, those should be measured
# separately, so assert that only desktop configurations exist.
KNOWN_RUN_CONFIGS = set([
    ('chrome', 'debian'),
    ('chrome', 'linux'),
    ('chrome', 'linux\n'),
    ('edge', 'windows'),
    ('firefox', 'debian'),
    ('firefox', 'linux'),
    ('safari', 'macos'),
    ('safari', 'macOS'),
])


def run_sha(run):
    return run['revision']


def run_date(run):
    return dateutil.parser.parse(run['created_at'])


def calculate_latencies(prs, runs):
    """For each PR, find the earliest run for each browser that included that PR,
    and calucate the latencies between the PR and the runs."""

    for run in runs:
        # If this assert fails, add to the known set if it's a desktop
        # configuration, otherwise filter out the run.
        assert (run['browser_name'], run['os_name']) in KNOWN_RUN_CONFIGS

    browsers = list(set(run['browser_name'] for run in runs))
    browsers.sort()

    # Per-browser latencies:
    for name in browsers:
        browser_runs = [run for run in runs if run['browser_name'] == name]
        latencies = get_pr_latencies(prs, events=browser_runs, event_sha=run_sha, event_date=run_date)
        csv_path = CSV_PATH_TEMPLATE.format(name)
        db = RunLatencyDB(csv_path)
        for entry in latencies:
            run = entry['event']
            if run is None:
                continue
            db.add({
                'PR': entry['pr']['PR'],
                'run_sha': run['revision'],
                'run_time': run['created_at'],
                'latency': entry['latency'],
            })
        db.write()


def main():
    prs = fetch_all_prs().values()
    runs_response = requests.get(RUNS_URL)
    runs_response.raise_for_status()
    runs = runs_response.json()
    calculate_latencies(prs, runs)


if __name__ == '__main__':
    main()
