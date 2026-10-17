#!/bin/sh
set -eu
# Initialise the mounted database, not an image-layer database hidden by the mount.
python init_db.py
exec "$@"
