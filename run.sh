#!/bin/bash

set -e

source .venv/bin/activate
alembic upgrade head
python -m bin.api
