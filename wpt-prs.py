#!/usr/bin/env python

from __future__ import print_function
import re
import subprocess

from csv_database import PRDB
from wpt_common import PRS_FILE, pr_number_from_tag, wpt_git


def get_merge_pr_tags():
    """Gets the set of merge_pr_* tags as string."""
    # --format="%(refname:strip=2) %(objectname)" would also include SHA-1
    return wpt_git(['tag', '--list', 'merge_pr_*']).splitlines()


def verify_pr_tags(prs):
    # sort PRs by commit date and assert that this matches commit DAG order
    sorted_prs = sorted(prs, key=lambda pr: pr['commit_date'])
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
        # --iso-strict-local works because TZ=UTC is set in the environment
        info = wpt_git(['log', '--no-walk', '--format=%H%n%cd%n%B',
                        '--date=iso-strict-local', pr_tag])
        lines = info.splitlines()

        commit = lines[0]
        commit_date = lines[1][0:19] + 'Z'
        chromium_commit = ''
        for line in lines[2:]:
            match = re.match(r'Change-Id: (.+)', line)
            if match is None:
                match = re.match(r'Cr-Commit-Position: (.+)', line)
            if match is not None:
                chromium_commit = match.group(1).strip()
                break

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
