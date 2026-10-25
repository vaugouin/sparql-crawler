#!/bin/bash
# Switch sparql-crawler.sh back on: removes the flag file CRON_OFF that off.sh wrote.
cd "$(dirname "$(readlink -f "$0")")" || exit 1
# A launcher renamed by the old off.sh (<name>-off.sh, before 2026-10-25) is put back,
# or dropped when git has already restored the tracked one.
[ -f sparql-crawler-off.sh ] && { [ -f sparql-crawler.sh ] && rm -f sparql-crawler-off.sh || mv sparql-crawler-off.sh sparql-crawler.sh; }
rm -f CRON_OFF && echo "sparql-crawler: on (CRON_OFF removed)"
