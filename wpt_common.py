"""A bunch of common functions shared by wpt-{import,export}-stats.
Python 6 (2 and 3 compatible) please.
"""

from __future__ import print_function
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
GH_AUTH = (GH_USER, GH_TOKEN) if (GH_USER and GH_TOKEN) else None
if GH_AUTH is None:
    print('Warning: Provide GH_USER and GH_TOKEN to get full results')

# GitHub cache. Delete the file to fetch PRs again.
CHROMIUM_PRS_FILE = 'prs-chromium.json'
NON_CHROMIUM_PRS_FILE = 'prs-others.json'

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

