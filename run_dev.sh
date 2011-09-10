#!/bin/sh
UWSGI="/home/fluxid/main/compiles/uwsgi-0.9.9.1/uwsgi"

WORKING_DIR="$(cd "${0%/*}" 2>/dev/null; dirname "$PWD"/"${0##*/}")"
cd ${WORKING_DIR}

$UWSGI --http 0.0.0.0:8080 --venv venv --file app.py
