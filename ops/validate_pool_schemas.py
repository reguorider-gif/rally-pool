#!/usr/bin/env python3
"""
Validate all JSON Schema files in the schemas/ directory.

Usage:
    python3 ops/validate_pool_schemas.py

Checks:
    1. Each file is valid JSON.
    2. If jsonschema package is available, validates schema structure (Draft 2020-12).
    3. Reports PASS/FAIL per file.
    4. Exits with non-zero code if any JSON parse fails.
"""

import json
import sys
import os
import glob

HAS_JSONSCHEMA = False
try:
    from jsonschema import Draft202012Validator, FormatChecker
    HAS_JSONSCHEMA = True
except ImportError:
    pass


def validate_json(filepath):
    """Parse a JSON file. Returns (parsed_object, error_string_or_None)."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, None
    except json.JSONDecodeError as e:
        return None, f"JSON parse error: {e}"
    except Exception as e:
        return None, f"Read error: {e}"


def validate_schema_structure(data, filepath):
    """Validate schema structure using jsonschema if available."""
    if not HAS_JSONSCHEMA:
        return "SKIPPED (jsonschema not installed)"
    try:
        schema = data
        # Check if it has $schema and a valid $id
        Draft202012Validator.check_schema(schema)
        return "PASS"
    except Exception as e:
        return f"FAIL: {e}"


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    schemas_dir = os.path.join(project_root, "schemas")

    if not os.path.isdir(schemas_dir):
        print(f"ERROR: schemas directory not found at {schemas_dir}")
        sys.exit(1)

    schema_files = sorted(glob.glob(os.path.join(schemas_dir, "*.schema.json")))

    if not schema_files:
        print("WARNING: No .schema.json files found in schemas/")
        sys.exit(0)

    print(f"Found {len(schema_files)} schema files in {schemas_dir}/\n")
    print(f"jsonschema package: {'available (Draft 2020-12)' if HAS_JSONSCHEMA else 'NOT installed (JSON parse check only)'}")
    print("=" * 70)

    all_json_valid = True
    results = []

    for filepath in schema_files:
        filename = os.path.basename(filepath)
        data, json_error = validate_json(filepath)

        if json_error:
            status = f"FAIL (JSON: {json_error})"
            all_json_valid = False
            schema_status = "N/A"
        else:
            status = "PASS"
            schema_status = validate_schema_structure(data, filepath)

        results.append((filename, status, schema_status))

    # Print results
    print(f"\n{'File':<35} {'JSON':<8} {'Schema':<30}")
    print("-" * 73)
    for filename, json_status, schema_status in results:
        print(f"{filename:<35} {json_status:<8} {schema_status:<30}")

    print("=" * 73)

    if all_json_valid:
        print(f"\nAll {len(schema_files)} schemas: JSON valid")
        if HAS_JSONSCHEMA:
            schema_passes = sum(1 for _, _, s in results if s == "PASS")
            print(f"Schema validation: {schema_passes}/{len(schema_files)} PASS")
        sys.exit(0)
    else:
        fails = sum(1 for _, s, _ in results if s.startswith("FAIL"))
        print(f"\nFAILED: {fails} schema(s) have JSON errors. Fix before proceeding.")
        sys.exit(1)


if __name__ == "__main__":
    main()
