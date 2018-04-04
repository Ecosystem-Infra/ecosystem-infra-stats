#!/usr/bin/env python

from __future__ import print_function
from collections import defaultdict
import dateutil.parser
import json
import requests

from wpt_common import CUTOFF, QUARTER_START, fetch_all_prs, get_pr_latencies, wpt_git

# 1000 because of https://github.com/w3c/wptdashboard/issues/524
RUNS_URL='https://wpt.fyi/api/runs?max-count=1000'
CSV_FILE = 'wpt-dashboard-latency.csv'

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


# There can be duplicate runs. Use the earliest run for each browser.
# See https://github.com/w3c/wptdashboard/issues/528.
def filter_unique_runs(runs):
    """Builds a mapping from browser name and wpt sha to earliest date, and
    then filters runs to just the runs in that mapping."""

    def key(run):
        return (run['browser_name'], run['revision'])

    earliest_dates = defaultdict(list)

    for run in runs:
        browser_and_sha = key(run)
        date = run['created_at']
        existing_date = earliest_dates.get(browser_and_sha)
        if existing_date is not None:
            if dateutil.parser.parse(existing_date) < dateutil.parser.parse(date):
                continue
        earliest_dates[browser_and_sha] = date

    return [run for run in runs if run['created_at'] == earliest_dates[key(run)]]


def event_from_run(run):
    """Return an event object for get_latencies."""
    return { 'sha': run['revision'], 'date': run['created_at'] }


def calculate_latencies(prs, runs):
    """For each PR, find the earliest run for each browser that included that PR,
    and calucate the latencies between the PR and the runs."""

    for run in runs:
        # If this assert fails, add to the known set if it's a desktop
        # configuration, otherwise filter out the run.
        assert (run['browser_name'], run['os_name']) in KNOWN_RUN_CONFIGS

    browsers = list(set(run['browser_name'] for run in runs))
    browsers.sort()

    # For each browser, create a list of events which is the completion of a
    # run for a given commit, as arguments for get_pr_latencies.
    for name in browsers:
        events = [event_from_run(run) for run in runs if run['browser_name'] == name]
        latencies = get_pr_latencies(prs, events)
        print(name, len(events), 'latencies:')
        #print(json.dumps(latencies, indent=2))
    return

    # Get the complete runs by starting with the union of all and intersecting
    # with the runs for each browser.
    complete_shas = set(run['revision'] for run in runs)
    for browser in browsers:
        browser_runs = (run['revision'] for run in runs if run['browser_name'] == browser)
        complete_shas.intersection_update(browser_runs)
    print(len(complete_shas), 'complete runs:')
    print(complete_shas)
    for sha in complete_shas:
        complete_runs = [run for run in runs if run['revision'] == sha]
        assert len(complete_runs) == len(browsers)


def main():
    prs = fetch_all_prs().values()
    runs = requests.get(RUNS_URL).json()
    unique_runs = filter_unique_runs(runs)
    calculate_latencies(prs, unique_runs)


if __name__ == '__main__':
    main()
