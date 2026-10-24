#!/bin/bash -i

set -ex

WORKSPACE_DIR="$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." && pwd )"

echo "Installing Poetry Project Dependencies"
find "${WORKSPACE_DIR}" -type f -name "pyproject.toml" -not -path "*/.venv/*" -execdir poetry install \;

echo "Configuring Pre-commit to run on Git Commit"
cd "${WORKSPACE_DIR}"
pre-commit install -c pre-commit-config.yaml

echo "Post Create Script Executed Successfully!"
