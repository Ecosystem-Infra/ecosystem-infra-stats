from datetime import datetime
import os
import subprocess
import sys

from dateutil.relativedelta import relativedelta

from csv_database import CommitDB

try:
    WPT_DIR = sys.argv[1]
except IndexError:
    WPT_DIR = os.path.expanduser('~/web-platform-tests/wpt')


def git(args, cwd):
    command = ['git'] + args
    output = subprocess.check_output(command, cwd=cwd, env={'TZ': 'UTC'})
    # Alright this only works in UTF-8 locales...
    return output.decode('utf-8').rstrip()


def wpt_git(args):
    return git(args, cwd=WPT_DIR)


COMMITS_CSV = 'wpt-commits.csv'


FIELD_GREP_ARGS = {
    'Total commits': [],
    'Chromium exports': [
        '--grep', '^Change-Id:',
        '--grep', '^Cr-Commit-Position:'
    ],
    'Gecko exports': [
        '--grep', '^Upstreamed from https://bugzilla\\.mozilla\\.org/',
        '--grep', '^gecko-commit:'
    ],
    'Servo exports': [
        '--grep', '^Upstreamed from https://github\\.com/servo/'
    ],
    'WebKit exports': [
        '--grep', '^WebKit export of https://bugs\\.webkit\\.org/'
    ],
}


def isoformat(dt):
    return dt.isoformat() + 'Z'


db = CommitDB(COMMITS_CSV)
now = datetime.now()
since = datetime(2015, 1, 1)

while since < now:
    until = since + relativedelta(months=1)
    args = ['rev-list', 'origin/master', '--count', '--no-merges',
            '--since', isoformat(since), '--until', isoformat(until)]
    record = {'Month': since.strftime('%Y-%m')}
    for field, grep_args in FIELD_GREP_ARGS.items():
        count = wpt_git(args + grep_args).strip()
        record[field] = count
    db.add(record)
    since = until

db.write()
