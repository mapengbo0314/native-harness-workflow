#!/bin/bash
# doc-state-router.sh - Queries manifest.json for doc states

MANIFEST_FILE="docs/manifest.json"
FORMAT="${1:-json}"

# Check if manifest exists
if [[ ! -f "$MANIFEST_FILE" ]]; then
    echo "✗ manifest.json not found at $MANIFEST_FILE" >&2
    exit 1
fi

# Validate JSON format
if ! jq empty "$MANIFEST_FILE" 2>/dev/null; then
    echo "✗ manifest.json is not valid JSON" >&2
    exit 2
fi

# Extract docs by state and output in requested format
if [[ "$FORMAT" == "json" ]]; then
    jq '{
        proposed_docs: [.docs[] | select(.state == "proposed") | .name],
        inprogress_docs: [.docs[] | select(.state == "inprogress") | .name],
        completed_docs: [.docs[] | select(.state == "completed") | .name],
        reference_docs: [.docs[] | select(.state == "reference") | .name]
    }' "$MANIFEST_FILE"
else
    # Text format
    proposed=$(jq -r '.docs[] | select(.state == "proposed") | .name' "$MANIFEST_FILE" | paste -sd ',' - || echo "(none)")
    inprogress=$(jq -r '.docs[] | select(.state == "inprogress") | .name' "$MANIFEST_FILE" | paste -sd ',' - || echo "(none)")
    completed=$(jq -r '.docs[] | select(.state == "completed") | .name' "$MANIFEST_FILE" | paste -sd ',' - || echo "(none)")
    reference=$(jq -r '.docs[] | select(.state == "reference") | .name' "$MANIFEST_FILE" | paste -sd ',' - || echo "(none)")

    echo "Proposed: $proposed"
    echo "In Progress: $inprogress"
    echo "Completed: $completed"
    echo "Reference: $reference"
fi

exit 0
