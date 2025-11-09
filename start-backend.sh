#!/bin/bash
# Script to start backend with environment variables from parent directory

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PARENT_DIR="$(dirname "$SCRIPT_DIR")"

# Source the .env file from parent directory
if [ -f "$PARENT_DIR/.env" ]; then
    echo "Loading environment variables from $PARENT_DIR/.env"
    set -a
    source "$PARENT_DIR/.env"
    set +a
else
    echo "Warning: .env file not found at $PARENT_DIR/.env"
fi

# Change to script directory
cd "$SCRIPT_DIR"

# Run docker-compose
docker-compose -f docker-compose.prod.yml up -d app

