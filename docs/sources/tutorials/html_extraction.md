# HTML File Extraction #

Obtain an HTML file and use the CLI to extract the contents.
```bash
# curl a file to use
curl -L https://www.python.org -o python.html

# Main command
unifile python.html --out results.jsonl --html-export extracted.html
```

**NOTE**: Under the hood, the "Main command" above is converted to this command and executed.
```bash
unifile extract python.html --out results.jsonl --html-export extracted.html
```