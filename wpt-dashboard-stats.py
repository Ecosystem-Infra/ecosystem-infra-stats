#!/usr/bin/env python

import dateutil.parser
import requests

from csv_database import RunLatencyDB
from wpt_common import CUTOFF, read_pr_db, get_pr_latencies

# max-count=1000 because of https://github.com/web-platform-tests/wpt.fyi/issues/3.
RUNS_URL_TEMPLATE = 'https://wpt.fyi/api/runs?max-count=1000&label=master&{}'
CSV_PATH_TEMPLATE = 'wpt-dashboard-{}-latencies.csv'

NAME_AND_QUERIES = [
    ('chrome-stable', 'product=chrome&label=stable'),
    ('edge-stable', 'product=edge&label=stable'),
    ('firefox-stable', 'product=firefox&label=stable'),
    ('safari-stable', 'product=safari&label=stable'),
    ('aligned-stable', 'products=chrome,edge,firefox,safari&label=stable&aligned'),
    ('chrome-experimental', 'product=chrome&label=experimental'),
    # ('edge-experimental', 'product=edge&label=experimental'),
    ('firefox-experimental', 'product=firefox&label=experimental'),
    ('safari-experimental', 'product=safari&label=experimental'),
    # ('aligned-experimental', 'products=chrome,edge,firefox,safari&label=experimental&aligned'),
]


def run_sha(run):
    return run['revision']


def run_date(run):
    return dateutil.parser.parse(run['created_at'])


def filter_runs(runs, sort_key=None, sort_reverse=False, filter_key=None):
    """Returns a list of runs filtered to the first (by sort_key) run
    considered a duplicate by filter_key. Skips runs before the cutoff."""

    cutoff_date = dateutil.parser.isoparse(CUTOFF)
    filtered_runs = {}
    for run in sorted(runs, key=sort_key, reverse=sort_reverse):
        if run_date(run) < cutoff_date:
            continue
        key = filter_key(run)
        if key not in filtered_runs:
            filtered_runs[key] = run
    return filtered_runs.values()


def write_latencies(prs, name, runs):
    """For each PR, find the earliest run that included that PR, and calucate
    the latencies between the PR and the runs. Write the results to a CSV
    file."""

    # Find the earliest run and filter out PRs associated with that run, as
    # all PRs that came before that will be associated with that single run.
    earliest_run = min(runs, key=run_date)

    latencies = get_pr_latencies(
        prs, events=runs, event_sha_func=run_sha, event_date_func=run_date)
    csv_path = CSV_PATH_TEMPLATE.format(name)
    db = RunLatencyDB(csv_path)
    for entry in latencies:
        run = entry['event']
        if run is None or run is earliest_run:
            continue
        pr = entry['pr']
        db.add({
            'PR': str(pr['PR']),
            'merge_sha': pr['merge_commit_sha'][0:10],
            'merge_date': pr['merged_at'],
            'run_sha': run['revision'],
            'run_date': run['created_at'],
            'latency': entry['latency'],
        })
    db.write(order='asc')


def analyze(prs, name, query):
    runs_url = RUNS_URL_TEMPLATE.format(query)
    runs_response = requests.get(runs_url)
    runs_response.raise_for_status()
    runs = runs_response.json()

    # There are runs before the cutoff and there can be duplicate runs. Use the
    # earliest run for each browser+revision, ignoring OS and any other
    # features of the run. See
    # https://github.com/web-platform-tests/wpt.fyi/issues/54.
    runs = filter_runs(runs, sort_key=run_date,
                       filter_key=lambda r: (r['browser_name'], r['revision']))

    # For aligned runs, filter to just the one with the latest run date
    if name.startswith('aligned-'):
        runs = filter_runs(runs, sort_key=run_date, sort_reverse=True,
                           filter_key=run_sha)

    print("Found {} unique {} runs".format(len(runs), name))
    write_latencies(prs, name, runs)


def main():
    prs = read_pr_db().values()
    for (name, query) in NAME_AND_QUERIES:
        analyze(prs, name, query)


if __name__ == '__main__':
    main()
