#!/bin/bash

# Usage message
usage() {
    echo "Usage: $0 <new-version> [--dry-run]"
    exit 1
}

# Parse arguments
DRY_RUN=false
NEW_VERSION=""

for arg in "$@"; do
    if [[ "$arg" == "--dry-run" ]]; then
        DRY_RUN=true
    else
        NEW_VERSION="$arg"
    fi
done

# Check if version is provided
if [[ -z "$NEW_VERSION" ]]; then
    usage
fi

# Function to check if the last command succeeded
check_command() {
    if [ $? -ne 0 ]; then
        echo "Error: $1"
        exit 1
    fi
}

echo "Preparing reset to version $NEW_VERSION"
if $DRY_RUN; then echo "Dry run mode enabled — no files or tags will be modified."; fi

# === TAG CLEANUP ===

echo "Finding local tags starting with 'v'..."
local_tags=$(git tag | grep '^v')
if $DRY_RUN; then
    echo "Would delete local tags:"
    echo "$local_tags"
else
    echo "$local_tags" | xargs -r git tag -d
    check_command "Failed to delete local tags"
fi

echo "Finding remote tags starting with 'v'..."
remote_tags=$(git ls-remote --tags origin | awk '{print $2}' | grep '^refs/tags/v' | sed 's|^refs/tags/||')
if $DRY_RUN; then
    echo "Would delete remote tags:"
    echo "$remote_tags"
else
    echo "$remote_tags" | xargs -r -n1 git push origin --delete
    check_command "Failed to delete remote tags"
fi

# === VERSION AND CHANGELOG ===

if $DRY_RUN; then
    echo "Would set Poetry version to $NEW_VERSION"
else
    echo "Resetting version to $NEW_VERSION..."
    poetry version "$NEW_VERSION"
    check_command "Failed to update version"
fi

if $DRY_RUN; then
    echo "Would update all versioned files"
    RAW_OUTPUT=$(scripts/update_versions.py "$NEW_VERSION" --dry-run 2>&1)
    echo "$RAW_OUTPUT" >&2
    UPDATED_FILES=$(echo "$RAW_OUTPUT" | grep -Eo 'DRYRUN: .+' | cut -d' ' -f2-)
else
    echo "Updating version in listed files..."
    RAW_OUTPUT=$(scripts/update_versions.py "$NEW_VERSION" 2>&1)
    echo "$RAW_OUTPUT" >&2
    check_command "Failed to update versioned files"
    UPDATED_FILES=$(echo "$RAW_OUTPUT" | grep -Eo 'UPDATED: .+' | cut -d' ' -f2-)
fi


if $DRY_RUN; then
    echo "Would create new CHANGELOG.md entry for $NEW_VERSION"
else
    echo "Creating new CHANGELOG.md..."
    TODAY=$(date +%F)
    cat > CHANGELOG.md << EOL
# Changelog

## [$NEW_VERSION] - $TODAY

### Initial Release
EOL
    check_command "Failed to create CHANGELOG.md"
fi

# === COMMIT AND PUSH ===

if $DRY_RUN; then
    echo "Would commit and push version $NEW_VERSION to main"
else
    echo "Committing changes..."
    echo "Staging updated version files and CHANGELOG.md..."
    git add $UPDATED_FILES CHANGELOG.md
    git commit -m "chore: reset version to $NEW_VERSION"
    check_command "Failed to commit changes"

    echo "Pushing changes..."
    git push origin main
    check_command "Failed to push changes"
fi

echo "✅ Version reset to $NEW_VERSION complete!"
