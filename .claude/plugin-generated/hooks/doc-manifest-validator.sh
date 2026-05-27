#!/bin/bash
# doc-manifest-validator.sh - Validates doc-system manifest.json

set -e

MANIFEST_FILE="docs/manifest.json"

# Check if manifest exists
if [[ ! -f "$MANIFEST_FILE" ]]; then
    echo "✗ manifest.json not found at $MANIFEST_FILE"
    exit 1
fi

# Validate JSON format
if ! jq empty "$MANIFEST_FILE" 2>/dev/null; then
    echo "✗ manifest.json is not valid JSON"
    exit 1
fi

# Validate manifest structure
if ! jq -e '.docs | type == "array"' "$MANIFEST_FILE" >/dev/null 2>&1; then
    echo "✗ manifest.json must contain a 'docs' array"
    exit 1
fi

# Validate each doc entry
errors=0
jq -r '.docs[] | "\(.name):\(.state)"' "$MANIFEST_FILE" | while IFS=':' read -r name state; do
    # Check required fields
    if [[ -z "$name" ]]; then
        echo "✗ Doc entry missing 'name' field"
        ((errors++))
    fi

    # Validate state value
    if [[ ! "$state" =~ ^(proposed|inprogress|completed|reference)$ ]]; then
        echo "✗ Doc '$name' has invalid state: $state (must be proposed|inprogress|completed|reference)"
        ((errors++))
    fi
done

if [[ $errors -gt 0 ]]; then
    exit 1
fi

# Check for required fields in each entry
missing_fields=$(jq '.docs[] | select(.created_date == null or .state == null or .name == null) | .name' "$MANIFEST_FILE" 2>/dev/null)
if [[ -n "$missing_fields" ]]; then
    echo "✗ Doc entries missing required fields (name, state, created_date): $missing_fields"
    exit 1
fi

echo "✓ manifest.json is valid"
exit 0
