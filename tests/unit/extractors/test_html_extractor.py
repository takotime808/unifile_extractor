# Copyright (c) 2025 takotime808

import pytest

from unifile import extract_to_table, ExtractionOptions

def test_html_blocks_and_tables(tmp_path):
    html = """
    <html><body>
      <h1>Title Here</h1>
      <p>Hello <b>world</b>.</p>
      <ul><li>First</li><li>Second</li></ul>
      <table>
        <tr><th>A</th><th>B</th></tr>
        <tr><td>1</td><td>2</td></tr>
      </table>
      <pre><code>print("code")</code></pre>
      <figcaption>A caption</figcaption>
    </body></html>
    """
    p = tmp_path / "sample.html"
    p.write_text(html, encoding="utf-8")

    df = extract_to_table(str(p), options=ExtractionOptions(enable_tables=True, enable_block_types=True))
    # Expect at least heading, paragraph, list items, table, code, caption
    btypes = [ (r.get("metadata") or {}).get("block_type") for _, r in df.iterrows() ]
    assert "heading" in btypes
    assert "paragraph" in btypes
    assert "list_item" in btypes
    assert "code" in btypes
    assert "caption" in btypes
    assert any(df.unit_type == "table")
    # Table content should contain tabs and newline
    table_rows = df[df.unit_type=="table"]
    assert "\t" in table_rows.iloc[0].content
