"""A bunch of common functions shared by wpt-{import,export}-stats.
Python 6 (2 and 3 compatible) please.
"""

# Requirements: python-dateutil, requests

from __future__ import print_function
from collections import defaultdict
import os
import re
import subprocess
import sys

import dateutil.parser
import requests

from csv_database import PRDB


# Only PRs after this time (UTC) will be processed. Our 2-way sync really
# started to stablize around this time. Earlier results are inaccurate.
CUTOFF = '2017-07-01T00:00:00Z'
# Change this when it is a new quarter.
QUARTER_START = '2018-01-01T00:00:00Z'

# Read tokens from env vars.
GH_USER = os.environ.get('GH_USER')
GH_TOKEN = os.environ.get('GH_TOKEN')
GH_AUTH = (GH_USER, GH_TOKEN) if (GH_USER and GH_TOKEN) else None
if GH_AUTH is None:
    print('Warning: Provide GH_USER and GH_TOKEN to get full results')

# GitHub cache. Delete the file to fetch PRs again.
PRS_FILE = 'wpt-prs.csv'

try:
    CHROMIUM_DIR = sys.argv[1]
except IndexError:
    CHROMIUM_DIR = os.path.expanduser('~/chromium/src')
CHROMIUM_WPT_PATH = 'third_party/WebKit/LayoutTests/external/wpt'
try:
    WPT_DIR = sys.argv[2]
except IndexError:
    WPT_DIR = os.path.expanduser('~/github/web-platform-tests')


def git(args, cwd):
    command = ['git'] + args
    output = subprocess.check_output(command, cwd=cwd)
    # Alright this only works in UTF-8 locales...
    return output.decode('utf-8').rstrip()


def chromium_git(args):
    return git(args, cwd=CHROMIUM_DIR)


def wpt_git(args):
    return git(args, cwd=WPT_DIR)


def github_request(url):
    base_url = 'https://api.github.com'
    res = requests.get(base_url + url, auth=GH_AUTH)
    return res.json()


def fetch_all_prs():
    try:
        pr_db = PRDB(PRS_FILE)
        pr_db.read()
        print('Read', len(pr_db), 'PRs from', PRS_FILE)
        return pr_db
        print('Fetching new PRs')
    except (IOError, AssertionError):
        pr_db = PRDB(PRS_FILE)
        print('Fetching all PRs')

    # Sorting by merged date is not supported, so we sort by created date
    # instead, which is good enough because a PR cannot be merged before
    # being created.
    base_url = ('/repos/w3c/web-platform-tests/pulls?'
                'sort=created&direction=desc&state=closed&per_page=100')

    cutoff = dateutil.parser.parse(CUTOFF)
    # 5000 is the rate limit. We'll break early.
    for page in range(1, 5000):
        print('Fetching page', page)
        url = base_url + '&page={}'.format(page)
        data = github_request(url)
        if not data:
            print('No items in page {}. Probably reached rate limit. Stopping.'
                  .format(page))
            break

        finished = False
        for pr in data:
            if not pr.get('merged_at'):
                # Abandoned PRs
                continue

            if dateutil.parser.parse(pr['merged_at']) < cutoff:
                print('Reached cutoff point. Stop fetching more PRs.')
                finished = True
                break
            if pr_db.get(pr['number']):
                print('No more new PRs')
                finished = True
                break

            chromium_commit = ''
            labels = [label['name'] for label in pr['labels']]
            if 'chromium-export' in labels:
                match = re.search(r'^Change-Id\: (.+)$', pr['body'], re.MULTILINE)
                try:
                    chromium_commit = match.groups()[0].strip()
                except AttributeError:
                    match = re.search(r'^Cr-Commit-Position\: (.+)$', pr['body'],
                                      re.MULTILINE)
                    try:
                        chromium_commit = match.groups()[0].strip()
                    except AttributeError:
                        pass
            pr_db.add({
                'PR': str(pr['number']),
                'merge_commit_sha': pr['merge_commit_sha'],
                'merged_at': pr['merged_at'],
                'author': pr['user']['login'],
                'chromium_commit': chromium_commit
            })
        if finished:
            break

    print('Fetched {} PRs created and merged after {}'
          .format(len(pr_db), CUTOFF))

    print('Writing file', PRS_FILE)
    pr_db.write(order='asc')
    return pr_db


def is_export_pr(pr):
    return bool(pr['chromium_commit'])


def pr_number_from_tag(tagish):
    """Extracts the PR number as integer from a string that begins with
    merge_pr*, like merge_pr_6581 or merge_pr_6589-1-gc9db8d86f6."""
    match = re.search(r'merge_pr_(\d+)', tagish)
    if match is not None:
        return int(match.group(1))
    return None


def get_tagged_prs():
    """Gets the set of integers for which merge_pr_* exists."""
    # --format="%(refname:strip=2) %(objectname)" would also include SHA-1
    output = wpt_git(['tag', '--list', 'merge_pr_*'])
    return set(pr_number_from_tag(tag) for tag in output.split() if tag)


def git_contained_pr(commit):
    """Returns the number of the latest contained PR of commit using git describe."""
    try:
        tag = wpt_git(['describe', '--tags', '--match', 'merge_pr_*', commit])
        return pr_number_from_tag(tag)
    except subprocess.CalledProcessError:
        return None


def pr_date(pr):
    return dateutil.parser.parse(pr['merged_at'])


def get_pr_latencies(prs, events=None, event_sha=None, event_date=None):
    """For each PR, find the earliest event that included that PR,
    and calucate the latencies between the PR and the event.

    Args:
        prs: list of PRs from fetch_all_prs()
        events: list of events in any format
        event_sha: function to get a sha from an event
        event_date: function to get a datetime.datetime from an event

    Returns list of { 'pr': pr, 'event': event, 'latency': latency } objects.
    """

    # Sort the PRs by merge date and filter out the ones that weren't tagged,
    # since we don't know at which commit they were merged, and their computed
    # latency can therefore be higher than the real latency. (Any PR which has
    # correct merge information via the GitHub API should also have a tag:
    # https://github.com/foolip/ecosystem-infra-stats/issues/6#issuecomment-375731858)
    tagged_prs = get_tagged_prs()
    prs = sorted(filter(lambda pr: int(pr['PR']) in tagged_prs, prs), key=pr_date)

    # We get PR-to-event latencies by the following process:
    #  1. For each event find the latest contained PR. This is done using git
    #     describe, and after this point the git commit graph doesn't matter.
    #     Not all events necessarily have a known contained PR at all.
    #  2. Reverse to a mapping from PR to event. Some PRs won't be the latest
    #     contained PR of any event, and if there are multiple events for a
    #     single PR only the earliest is saved.
    #  3. Walk the list of PR and associated events backwards, keeping track
    #     of the earliest event encountered so far. That is the event against
    #     which the latency for the PR is measured.

    # Step 1.
    event_prs = [git_contained_pr(event_sha(event)) for event in events]

    # Convenience to allow using None as a placeholder for no event.
    def earliest_event(event1, event2):
        if event1 is None:
            return event2
        if event2 is None:
            return event1
        return min(event1, event2, key=event_date)

    # Step 2.
    pr_events = [None for pr in prs]
    pr_number_to_index = dict(zip((int(pr['PR']) for pr in prs), range(len(prs))))
    for event, pr_number in zip(events, event_prs):
        index = pr_number_to_index.get(pr_number)
        if index is None:
            continue
        pr_events[index] = earliest_event(pr_events[index], event)

    # Step 3.
    latencies = [{ 'pr': pr, 'event': None, 'latency': None } for pr in prs]
    foo_event = None
    for event, result in reversed(zip(pr_events, latencies)):
        foo_event = earliest_event(foo_event, event)
        if foo_event is None:
            continue
        result['event'] = foo_event
        result['latency'] = (event_date(foo_event) - pr_date(result['pr'])).total_seconds() / 60
    return latencies
