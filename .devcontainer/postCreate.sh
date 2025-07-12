#!/bin/bash -i

set -ex

echo "Installing Poetry Project Dependencies"
find /workspaces/satgus-trmnl -type f -name "pyproject.toml" -execdir poetry install \;

echo "Configuring Pre-commit to run on Git Commit"
pre-commit install

echo "Post Create Script Executed Successfully!"
