#!/bin/bash

# Copy the commit-msg hook to the .git/hooks directory
cp scripts/hooks/commit-msg .git/hooks/commit-msg

# Make the hook executable
chmod +x .git/hooks/commit-msg

echo "Git hook installed successfully."