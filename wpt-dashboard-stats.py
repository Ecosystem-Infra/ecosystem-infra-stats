#!/usr/bin/env python

import dateutil.parser
import requests

from csv_database import RunLatencyDB
from wpt_common import fetch_all_prs, get_pr_latencies

# 1000 because of https://github.com/w3c/wptdashboard/issues/524
RUNS_URL = 'https://wpt.fyi/api/runs?max-count=1000'
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


def filter_runs(runs, sort_key=None, sort_reverse=False, filter_key=None):
    """Returns a list of runs filtered to the first (by sort_key) run
    considered a duplicate by filter_key."""

    filtered_runs = {}
    for run in sorted(runs, key=sort_key, reverse=sort_reverse):
        key = filter_key(run)
        if key not in filtered_runs:
            filtered_runs[key] = run
    return filtered_runs.values()


def write_latencies(prs, runs, name):
    """For each PR, find the earliest run that included that PR, and calucate
    the latencies between the PR and the runs. Write the results to a CSV
    file."""

    latencies = get_pr_latencies(
        prs, events=runs, event_sha_func=run_sha, event_date_func=run_date)
    csv_path = CSV_PATH_TEMPLATE.format(name)
    db = RunLatencyDB(csv_path)
    for entry in latencies:
        run = entry['event']
        if run is None:
            continue
        db.add({
            'PR': str(entry['pr']['PR']),
            'run_sha': run['revision'],
            'run_time': run['created_at'],
            'latency': entry['latency'],
        })
    db.write(order='asc')


def analyze(prs, runs):
    for run in runs:
        # If this assert fails, add to the known set if it's a desktop
        # configuration, otherwise filter out the run.
        assert (run['browser_name'], run['os_name']) in KNOWN_RUN_CONFIGS

    # There can be duplicate runs. Use the earliest run for each
    # browser+revision, ignoring OS and any other features of the run.
    # See https://github.com/w3c/wptdashboard/issues/528.
    runs = filter_runs(runs, sort_key=run_date,
                       filter_key=lambda r: (r['browser_name'], r['revision']))

    browsers = list(set(run['browser_name'] for run in runs))
    browsers.sort()

    # Find complete runs by starting with the union of all commits and
    # intersecting with the runs for each browser in the below loop.
    complete_shas = set(map(run_sha, runs))

    # Per-browser latencies:
    for name in browsers:
        browser_runs = [r for r in runs if r['browser_name'] == name]
        complete_shas.intersection_update(set(map(run_sha, browser_runs)))
        print("Found {} unique {} runs".format(len(browser_runs), name))
        write_latencies(prs, browser_runs, name)

    # Group latency: keep the latest run for each revision, as that's when the
    # results became complete.
    complete_shas_runs = (r for r in runs if r['revision'] in complete_shas)
    complete_runs = filter_runs(complete_shas_runs, sort_key=run_date,
                                sort_reverse=True, filter_key=run_sha)
    print("Found {} complete ({}) runs".format(
        len(complete_runs), ', '.join(browsers)))
    write_latencies(prs, complete_runs, 'desktop')


def main():
    prs = fetch_all_prs().values()
    runs_response = requests.get(RUNS_URL)
    runs_response.raise_for_status()
    runs = runs_response.json()
    analyze(prs, runs)


if __name__ == '__main__':
    main()
