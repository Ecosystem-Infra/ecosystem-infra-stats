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

git config user.email "bot@foolip.org"
git config user.name "Automat af Ekosystem"
git add -A
git commit -m "Automatic update" -m "Using commit $COMMIT"
git push
