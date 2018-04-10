#!/usr/bin/env python
# Requirements: python-dateutil, numpy, requests

from __future__ import print_function
from collections import defaultdict, namedtuple
import csv
import dateutil.parser
import json
import numpy
import re
import requests
import subprocess

from wpt_common import CUTOFF, QUARTER_START, fetch_all_prs, wpt_git

RUNS_URL = 'https://wpt.fyi/api/runs?max-count=100'
CSV_FILE = 'wpt-dashboard-latency.csv'


def get_latencies(prs, runs):
    """For each PR, find the earliest run for each browser that included that PR,
    and calucate the latencies between the PR and the runs."""
    latencies = {}
    return latencies


def main():
    prs = fetch_all_prs()
    runs = requests.get(RUNS_URL).json()
    latencies = get_latencies(prs, runs)
    print(latencies)


if __name__ == '__main__':
    main()
