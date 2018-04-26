#!/usr/bin/env python

from __future__ import print_function
import dateutil.parser
import re
import subprocess

from csv_database import PRDB
from wpt_common import PRS_FILE, pr_number_from_tag, wpt_git


def get_merge_pr_tags():
    """Gets the set of merge_pr_* tags as string."""
    # --format="%(refname:strip=2) %(objectname)" would also include SHA-1
    return wpt_git(['tag', '--list', 'merge_pr_*']).splitlines()

def pr_commit_date(pr):
    return dateutil.parser.isoparse(pr['commit_date'])

def verify_pr_tags(prs):
    # sort PRs by commit date and assert that this matches commit DAG order
    sorted_prs = sorted(prs, key=pr_commit_date)
    for pr, next_pr in zip(sorted_prs, sorted_prs[1:]):
        try:
            wpt_git(['merge-base', '--is-ancestor', pr['tag'], next_pr['tag']])
        except subprocess.CalledProcessError:
            print('Expected {} ({}) to be an ancestor of'
                  '{} ({}) based on commit dates.'
                  .format(pr['tag'], pr['commit_date'],
                          next_pr['tag'], next_pr['commit_date']))
            print('When this is not the case, the commit dates of merge_pr_*'
                  'tags cannot be trusted.')
            exit(1)


def write_pr_db():
    prs = []
    for pr_tag in get_merge_pr_tags():
        info = wpt_git(['log', '--no-walk', '--format=%H|%cI|%B', pr_tag])
        commit, commit_date, commit_message = lines = info.split('|', 2)

        chromium_commit = ''
        match = re.search(r'^Change-Id: (.+)$', commit_message, re.MULTILINE)
        if match is None:
            match = re.search(r'^Cr-Commit-Position: (.+)$',
                              commit_message, re.MULTILINE)
        if match is not None:
            chromium_commit = match.group(1).strip()

        prs.append({
            'tag': pr_tag,
            'commit': commit,
            'commit_date': commit_date,
            'chromium_commit': chromium_commit
        })

    print('Verifying that commit date order matches commit graph order')
    verify_pr_tags(prs)

    pr_db = PRDB(PRS_FILE)
    for pr in prs:
        pr_db.add({
            'PR': str(pr_number_from_tag(pr['tag'])),
            'merge_commit_sha': pr['commit'],
            'merged_at': pr['commit_date'],
            'chromium_commit': pr['chromium_commit']
        })
    pr_db.write(order='asc')

    print('Wrote {} PRs to {}'.format(len(pr_db), PRS_FILE))
    return pr_db


def main():
    write_pr_db()


if __name__ == '__main__':
    main()
