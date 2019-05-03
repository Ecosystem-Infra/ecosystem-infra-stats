#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

COMMIT="$(git rev-parse HEAD)"

rm -rf gh-pages
git clone --branch gh-pages git@github.com:foolip/ecosystem-infra-stats.git gh-pages

rm -rf gh-pages/*
cp -r out/ecosystem-infra-stats/* gh-pages/

cd gh-pages

git add -A
git commit -m "Update stats" -m "Using commit $COMMIT"
git push
