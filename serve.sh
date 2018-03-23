#!/bin/bash
set -o errexit
set -o nounset
set -o pipefail

cd out

# https://docs.python.org/3/library/http.server.html#module-http.server
python3 -m http.server 8000 --bind 127.0.0.1
