# HTML File Extraction #

Obtain an HTML file and use the CLI to extract the contents.
```bash
# curl a file to use
curl -L https://www.kdedirect.com/collections/uas-multi-rotor-brushless-motors -o example.html

# Main command
unifile example.html --out results.jsonl --html-export extracted.html
```

**NOTE**: Under the hood, the "Main command" above is converted to this command and executed.
```bash
unifile extract example.html --out results.jsonl --html-export extracted.html
```