#!/usr/bin/python2
# Based off https://gist.github.com/jeffcarp/f1fb015e38f50e82d30b8c69b67faa74
# Requirements: numpy & requests ( sudo apt install python-{numpy,requests} )

from __future__ import print_function
from datetime import datetime
import csv
import collections
import json
import numpy
import os
import requests
import re
import subprocess


# Only PRs after this time (UTC) will be processed.
CUTOFF = '2017-01-01T00:00:00Z'
CHROMIUM_DIR = sys.argv[1]
# Provide GitHub token to get full results (otherwise limited to <500 PRs).
GH_USER = ''
GH_TOKEN = ''
# Target SLA (in minutes).
SLA = 60
# GitHub cache. Remove to fetch PRs again.
PRS_FILE = 'prs.json'
# Result files.
MINS_FILE = 'mins.json'
CSV_FILE = 'export-latencies.csv'


def fetch_all_prs():
    try:
        with open(PRS_FILE) as f:
            all_prs = json.load(f)
            print('Read', len(all_prs), 'from', PRS_FILE)
            return all_prs
    except Exception:
        pass

    print('Fetching all PRs')
    base_url = 'https://api.github.com/search/issues?q=repo:w3c/web-platform-tests%20type:pr%20label:chromium-export%20is:merged'
    github_oauth = (GH_USER, GH_TOKEN) if GH_TOKEN else None

    res = requests.get(base_url, auth=github_oauth)
    data = res.json()

    total = data['total_count']

    print(total, 'total PRs')

    page_size = 50
    total_pages = int(total / page_size) + 1

    prs = []

    for page in range(1, total_pages + 1):
        print('Fetching page', page)
        res = requests.get('{}&page={}&per_page={}'.format(base_url, page, page_size),
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


def _parse_github_time(timestr):
    return datetime.strptime(timestr, '%Y-%m-%dT%H:%M:%SZ')


def filter_prs(prs, cutoff):
    cutoff_time = _parse_github_time(cutoff)
    filtered_prs = []
    for pr in prs:
        pr_closed_at = _parse_github_time(pr['closed_at'])
        if pr_closed_at >= cutoff_time:
            filtered_prs.append(pr)
    print(len(filtered_prs), 'merged since', cutoff)
    return filtered_prs


def get_sha_from_change_id(change_id):
    grep = '^Change-Id: ' + change_id + '$'
    cmd = ['git', 'log', 'origin/master', '--format=%H', '-1', '--grep=%s' % grep]
    print(' '.join(cmd))
    p = subprocess.Popen(cmd, cwd=CHROMIUM_DIR, stdout=subprocess.PIPE)
    p.wait()

    sha = p.stdout.readline().strip()
    if len(sha) == 40:
        return sha
    else:
        return None


def get_sha_from_commit_position(commit_position):
    cmd = ['git', 'crrev-parse', commit_position]
    print(' '.join(cmd))
    p = subprocess.Popen(cmd, cwd=CHROMIUM_DIR, stdout=subprocess.PIPE)
    p.wait()

    sha = p.stdout.readline().strip()
    if len(sha) == 40:
        return sha
    else:
        return None


def _parse_git_time(timestr):
    return datetime.strptime(timestr, '%Y-%m-%dT%H:%M:%S+00:00')


def calculate_pr_delays(prs):
    min_differences = []
    min_differences_by_month = collections.defaultdict(list)
    skipped = []
    total_prs = len(prs)

    for index, pr in enumerate(prs):
        pr_number = pr['number']
        print('[%d/%d] PR: https://github.com/w3c/web-platform-tests/pull/%s' % (index+1, total_prs, pr['number']))
        pr_closed_at = _parse_github_time(pr['closed_at'])

        match = re.search('^Change-Id\: (.+)$', pr['body'], re.MULTILINE)

        try:
            change_id = match.groups()[0].strip()
            print('Found Change-Id', change_id)
            sha = get_sha_from_change_id(change_id)
        except AttributeError as e:
            print('Could not get Change-Id from PR, trying Cr-Commit-Position')
            match = re.search('^Cr-Commit-Position\: (.+)$', pr['body'], re.MULTILINE)

            try:
                commit_position = match.groups()[0].strip()
                print('Found Cr-Commit-Position', commit_position)
                sha = get_sha_from_commit_position(commit_position)
            except AttributeError as e:
                sha = None

        if sha is None:
            print('Unable to find commit. SKIPPING!')
            skipped.append(pr_number)
            continue

        print('Found SHA', sha)

        p = subprocess.Popen(['git', 'show', '-s', '--format=%cI', sha], cwd=CHROMIUM_DIR, stdout=subprocess.PIPE)
        p.wait()
        commit_time = _parse_git_time(p.stdout.readline().strip())

        print('Committed at', commit_time)
        print('PR closed at', pr_closed_at)
        mins_difference = (pr_closed_at - commit_time).total_seconds() / 60
        print('Delay (mins):', mins_difference)
        if mins_difference < 0:
            print('Negative delay. SKIPPING!')
            skipped.append(pr_number)
            continue

        min_differences.append(mins_difference)
        datekey = commit_time.strftime('%Y-%m')
        min_differences_by_month[datekey].append(mins_difference)

    if skipped:
        print('Skipped PRs:', skipped)

    items = min_differences_by_month.items()
    items = sorted(items, reverse=True, key=lambda i: i[0])
    print(items)

    print('Writing file', MINS_FILE)
    with open(MINS_FILE, 'w') as f:
        json.dump(min_differences, f)

    print('NOTE: Results eariler than cutoff time (%s) are not accurate.' % CUTOFF)
    print('Writing file', CSV_FILE)
    sla_field = '% meeting SLA ({} mins)'.format(SLA)
    with open(CSV_FILE, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['Month', '50th percentile', '90th percentile', 'Average', sla_field])
        writer.writeheader()
        for key, diffs in items:
            np_diffs = numpy.asarray(diffs)
            month_stat = {
                'Month': key,
                '50th percentile': numpy.percentile(np_diffs, 50),
                '90th percentile': numpy.percentile(np_diffs, 90),
                sla_field: (np_diffs <= SLA).sum() / float(len(np_diffs)),
                'Average': numpy.average(np_diffs),
            }
            print(month_stat)
            writer.writerow(month_stat)

    return min_differences


def analyze_mins(min_differences):
    out_of_sla = []
    in_sla = []
    total = len(min_differences)
    for mins in min_differences:
        if mins > 24 * 60:
            out_of_sla.append(mins)
        if mins < 25:
            in_sla.append(mins)

    average = numpy.average(min_differences)
    print('Since', CUTOFF, '(PR merge time):')
    print('Average CL committed to PR merged latency:', average, 'minutes')
    print(len(out_of_sla), '/', total, 'PRs out of 24H SLA -', float(len(out_of_sla)) / total)
    print(len(in_sla), '/', total, 'PRs inside 25m SLA -', float(len(in_sla)) / total)

    print('50th percentile', numpy.percentile(min_differences, 50))
    print('90th percentile', numpy.percentile(min_differences, 90))


def main():
    all_prs = fetch_all_prs()
    filtered_prs = filter_prs(all_prs, CUTOFF)
    min_differences = calculate_pr_delays(filtered_prs)
    analyze_mins(min_differences)


if __name__ == '__main__':
    main()
