# Schema Reference

The extractor emits rows conforming to the versioned schema defined in
`schema_v1.json`. Columns appear in a fixed order:

| column      | type                     | description |
|-------------|--------------------------|-------------|
| `source`    | string                   | Absolute path to the input file |
| `relpath`   | string                   | Path relative to the batch root |
| `kind`      | string                   | Logical unit type (`page`, `frame`, `email`, ...) |
| `page`      | integer or null          | Page or sequence number |
| `block`     | integer, string or null  | Block identifier within the page |
| `bbox`      | array or null            | Bounding box `[x0, y0, x1, y1]` |
| `text`      | string                   | Extracted text content |
| `confidence`| number or null           | OCR confidence when available |
| `mime`      | string or null           | Detected MIME type |
| `ts`        | string or null           | Timestamps for audio/video rows |
| `extra`     | object or null           | Additional extractor-specific metadata |

## Stability

Schema versions follow a stability guarantee:

* **Major version (`v1`)** – breaking changes may occur when the major version increments.
* **Minor additions** – within `v1` new columns may be appended but existing names and order remain
  stable, so downstream consumers can safely upgrade.
* **Removals or type changes** will only happen in a new major version.
