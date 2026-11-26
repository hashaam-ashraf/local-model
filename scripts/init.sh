#!/bin/sh
# Runs before the api starts (see deploy/Dockerfile). A failing step stops the container.
set -e

echo "Initializing container ..."

python -m scripts.create_database
alembic upgrade head
python -m scripts.seed_admin
