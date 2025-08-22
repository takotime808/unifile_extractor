# curl a file
curl -L https://www.python.org -o python.html

# Main command
unifile python.html --out results.jsonl --html-export extracted.html

# (Under the hood, the main command is converted to this command and executed)
unifile extract python.html --out results.jsonl --html-export extracted.html
