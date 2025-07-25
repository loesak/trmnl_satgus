#!/bin/bash -l

set -e

WORKING_DIR="$( dirname -- "${BASH_SOURCE[0]}" )"
cd ${WORKING_DIR}

echo "--------------------------------------------------"
echo "running poetry install"
poetry install

echo "--------------------------------------------------"
echo "running black"
poetry run black -v .

echo "--------------------------------------------------"
echo "running flake8"
poetry run flake8

echo "--------------------------------------------------"
echo "running mypy"
poetry run mypy .

echo "--------------------------------------------------"
echo "running isort"
poetry run isort .

echo "--------------------------------------------------"
echo "running bandit"
poetry run bandit -c pyproject.toml -ll -r .

echo "--------------------------------------------------"
echo "running pytest"
poetry run pytest tests/
