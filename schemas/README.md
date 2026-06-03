# AI Judge Pool Schemas

JSON Schema contracts for the prediction pool data pipeline.

## Convention

- All schemas use JSON Schema Draft 2020-12.
- Enums are defined in `pool.common.schema.json` and referenced via `$ref`.
- Each schema is standalone-valid (no external file dependencies for basic validation).
- Sample data lives in `data/pool/samples/`.
