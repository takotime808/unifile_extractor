# Usage Instructions #

Once this library is installed, it can be called from CLI:

List supported types:
```bash
unifile list-types
```

Extract from a local file and print to stdout:
```bash
unifile extract ./docs/sources/_static/data/sample-engineering-drawing.pdf --max-rows 50 --max-colwidth 120
```

Extract from a URL and save to Parquet:
```bash
unifile extract "https://www.fastradius.com/wp-content/uploads/2022/02/sample-engineering-drawing.pdf" --out drawing.parquet
```