#!/usr/bin/env python
# History: https://gist.github.com/jeffcarp/f1fb015e38f50e82d30b8c69b67faa74
#          https://gist.github.com/Hexcles/ec811c9dd45a0f21bb3fc3243bfa857a
# Requirements: python-datautil, numpy & requests

from __future__ import print_function
import csv
import collections
import dateutil.parser
import json
import numpy
import re

# FIXME: I know this is bad...
from wpt_common import *


# Target SLA (in minutes).
SLA = 60
# Cache file.
PRS_FILE = 'prs-chromium.json'
# Result files.
MINS_FILE = 'export-mins.json'
CSV_FILE = 'export-latencies.csv'

_GITHUB_DATE_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


def fetch_all_prs():
    try:
        with open(PRS_FILE) as f:
            all_prs = json.load(f)
            print('Read', len(all_prs), 'PRs from', PRS_FILE)
            return all_prs
    except (IOError, ValueError):
        pass

    print('Fetching all PRs')

    base_url = ('/search/issues?q='
           'repo:w3c/web-platform-tests%20'
           'type:pr%20'
           'is:merged%20'
           'label:chromium-export')

    init_data = github_request(base_url)
    total = init_data['total_count']
    print(total, 'total PRs')

    page_size = 100
    total_pages = int(total / page_size) + 1

    prs = []

    cutoff = dateutil.parser.parse(CUTOFF)
    for page in range(1, total_pages + 1):
        print('Fetching page', page)
        url = base_url + '&page={}&per_page={}'.format(page, page_size)
        data = github_request(url)
        if 'items' not in data:
            print('No items in page {}. Probably reached rate limit. Stopping.'
                  .format(page))
            break
        prs.extend(data['items'])

        last_item_closed_at = data['items'][-1]['closed_at']
        if dateutil.parser.parse(last_item_closed_at) < cutoff:
            print('Reached cutoff point. Stop fetching more PRs.')
            break

    print('Fetched', len(prs), 'merged PRs with chromium-export label')

    print('Writing file', PRS_FILE)
    with open(PRS_FILE, 'w') as f:
        json.dump(prs, f)
    return prs


def get_sha_from_change_id(change_id):
    grep = '^Change-Id: ' + change_id + '$'
    args = ['log', 'origin/master', '--format=%H', '-1', '--grep=%s' % grep]
    sha = chromium_git(args)
    if len(sha) == 40:
        return sha
    else:
        return None


def get_sha_from_commit_position(commit_position):
    args = ['crrev-parse', commit_position]
    sha = chromium_git(args)
    if len(sha) == 40:
        return sha
    else:
        return None


def calculate_pr_delays(prs):
    try:
        with open(MINS_FILE) as f:
            min_differences = json.load(f)
            print('Read', len(min_differences), 'results from', MINS_FILE)
            return min_differences
    except (IOError, ValueError):
        pass

    min_differences = {}
    skipped = []
    total_prs = len(prs)

    for index, pr in enumerate(prs):
        pr_number = pr['number']
        print('[{}/{}] PR: {}'.format(index+1, total_prs, pr['html_url']))
        pr_closed_at = dateutil.parser.parse(pr['closed_at'])

        match = re.search(r'^Change-Id\: (.+)$', pr['body'], re.MULTILINE)

        try:
            change_id = match.groups()[0].strip()
            print('Found Change-Id', change_id)
            sha = get_sha_from_change_id(change_id)
        except AttributeError:
            print('Could not get Change-Id from PR, trying Cr-Commit-Position')
            match = re.search(r'^Cr-Commit-Position\: (.+)$', pr['body'],
                              re.MULTILINE)

            try:
                commit_position = match.groups()[0].strip()
                print('Found Cr-Commit-Position', commit_position)
                sha = get_sha_from_commit_position(commit_position)
            except AttributeError:
                sha = None

        if sha is None:
            print('Unable to find commit. SKIPPING!')
            skipped.append(pr_number)
            continue

        print('Found SHA', sha)

        output = chromium_git(['show', '-s', '--format=%cI', sha])
        commit_time = dateutil.parser.parse(output)
        mins_difference = (pr_closed_at - commit_time).total_seconds() / 60

        print('Committed at', commit_time)
        print('PR closed at', pr_closed_at)
        print('Delay (mins):', mins_difference)
        if mins_difference < 0:
            print('Negative delay. SKIPPING!')
            skipped.append(pr_number)
            continue

        datekey = commit_time.strftime('%Y-%m')
        min_differences[pr_number] = {
            'latency': mins_difference,
            'month': datekey,
            'time': commit_time.strftime(_GITHUB_DATE_FORMAT)
        }

    if skipped:
        print('Skipped PRs:', skipped)

    print('Writing file', MINS_FILE)
    with open(MINS_FILE, 'w') as f:
        json.dump(min_differences, f)

    return min_differences


def analyze_mins(min_differences):
    min_differences_by_month = collections.defaultdict(list)
    this_quarter = []
    quarter_cutoff = dateutil.parser.parse(QUARTER_START)
    for datapoint in min_differences.values():
        min_differences_by_month[datapoint['month']].append(
            datapoint['latency'])
        if dateutil.parser.parse(datapoint['time']) >= quarter_cutoff:
            this_quarter.append(datapoint['latency'])

    print('NOTE: Results eariler than cutoff time ({}) are not accurate.'
          .format(CUTOFF))
    print('Writing file', CSV_FILE)
    sla_field = '% meeting SLA ({} mins)'.format(SLA)
    with open(CSV_FILE, 'w') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=[
            'Month', '50th percentile', '90th percentile', 'Average', 'PRs', sla_field])
        writer.writeheader()
        for month in sorted(min_differences_by_month.keys()):
            np_diffs = numpy.asarray(min_differences_by_month[month])
            num_prs = len(np_diffs)
            month_stat = {
                'Month': month,
                '50th percentile': numpy.percentile(np_diffs, 50),
                '90th percentile': numpy.percentile(np_diffs, 90),
                'Average': numpy.average(np_diffs),
                'PRs': num_prs,
                sla_field: (np_diffs <= SLA).sum() / float(num_prs),
            }
            writer.writerow(month_stat)

    quarter_total = len(this_quarter)
    np_this_quarter = numpy.asarray(this_quarter)
    average = numpy.average(np_this_quarter)
    out_of_sla = (np_this_quarter > SLA).sum()
    print('This quarter since', QUARTER_START, '(PR merge time):')
    print('Average CL committed to PR merged latency:', average, 'minutes')
    print('Quarter 50th percentile', numpy.percentile(np_this_quarter, 50))
    print('Quarter 90th percentile', numpy.percentile(np_this_quarter, 90))
    print('{} / {} PRs out of {} min SLA ({})'.format(
        out_of_sla, quarter_total, SLA, out_of_sla / float(quarter_total)))
    print('KR: (in_sla - 0.5) * 2 = ',
          ((quarter_total - out_of_sla) / float(quarter_total) - 0.5) * 2)


def main():
    all_prs = fetch_all_prs()
    min_differences = calculate_pr_delays(all_prs)
    analyze_mins(min_differences)


if __name__ == '__main__':
    main()
