"""A bunch of common functions shared by wpt-{import,export}-stats.
Python 6 (2 and 3 compatible) please.
"""

# Requirements: python-dateutil, requests

from __future__ import print_function
import dateutil.parser
import json
import os
import requests
import subprocess
import sys

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
PRS_FILE = 'wpt-prs.json'

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
        with open(PRS_FILE) as f:
            all_prs = json.load(f)
            print('Read', len(all_prs), 'PRs from', PRS_FILE)
            return all_prs
    except (IOError, ValueError):
        pass

    print('Fetching all PRs')

    # Sorting by merged date is not supported, so we sort by created date
    # instead, which is good enough because a PR cannot be merged before
    # being created.
    base_url = ('/repos/w3c/web-platform-tests/pulls?'
                'sort=created&direction=desc&state=closed')
    prs = []

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
                continue
            if dateutil.parser.parse(pr['merged_at']) < cutoff:
                print('Reached cutoff point. Stop fetching more PRs.')
                finished = True
                break
            prs.append(pr)
        if finished:
            break

    print('Fetched {} PRs created and merged after {}'
          .format(len(prs), CUTOFF))

    print('Writing file', PRS_FILE)
    with open(PRS_FILE, 'w') as f:
        json.dump(prs, f, indent=2)
    return prs


def is_export_pr(pr):
    labels = [label['name'] for label in pr['labels']]
    has_export_label = 'chromium-export' in labels
    if pr['user']['login'] == 'chromium-wpt-export-bot':
        assert has_export_label, '{} is missing the chromium-export label'.format(pr['html_url'])
    return has_export_label
