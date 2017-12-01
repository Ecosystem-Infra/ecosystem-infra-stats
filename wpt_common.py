"""A bunch of common functions shared by wpt-{import,export}-stats.
Python 3 please.
"""

from __future__ import print_function
import json
import os
import requests
import sys
import subprocess

# Only PRs after this time (UTC) will be processed. Our 2-way sync really
# started to stablize around this time. Earlier results are inaccurate.
CUTOFF = '2017-07-01T00:00:00Z'
# Change this when it is a new quarter.
QUARTER_START = '2017-10-01T00:00:00Z'

# Read tokens from env vars.
GH_USER = os.environ.get('GH_USER')
GH_TOKEN = os.environ.get('GH_TOKEN')

# GitHub cache. Delete the file to fetch PRs again.
PRS_FILE = 'prs.json'

try:
    CHROMIUM_DIR = sys.argv[1]
except IndexError:
    CHROMIUM_DIR = os.path.expanduser('~/chromium/src')

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


def fetch_all_prs():
    try:
        with open(PRS_FILE) as f:
            all_prs = json.load(f)
            print('Read', len(all_prs), 'PRs from', PRS_FILE)
            return all_prs
    except Exception:
        pass

    print('Fetching all PRs')
    base_url = 'https://api.github.com/search/issues?q=repo:w3c/web-platform-tests%20type:pr%20label:chromium-export%20is:merged'
    github_oauth = (GH_USER, GH_TOKEN) if (GH_USER and GH_TOKEN) else None
    if github_oauth is None:
        print('Warning: Provide GH_USER and GH_TOKEN to get full results (otherwise limited to <500 PRs)')

    res = requests.get(base_url, auth=github_oauth)
    data = res.json()

    total = data['total_count']

    print(total, 'total PRs')

    page_size = 50
    total_pages = int(total / page_size) + 1

    prs = []

    for page in range(1, total_pages + 1):
        print('Fetching page', page)
        res = requests.get(
            '{}&page={}&per_page={}'.format(base_url, page, page_size),
            auth=github_oauth)
        data = res.json()
        if 'items' not in data:
            print('No items in page', page, 'stopping')
            break
        prs.extend(data['items'])

    print('Fetched', len(prs), 'merged PRs with chromium-export label')

    print('Writing file', PRS_FILE)
    with open(PRS_FILE, 'w') as f:
        json.dump(prs, f)
    return prs
