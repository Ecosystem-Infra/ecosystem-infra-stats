#!/usr/bin/env python

from wpt_common import fetch_all_prs


def main():
    fetch_all_prs(update=True)


if __name__ == '__main__':
    main()
