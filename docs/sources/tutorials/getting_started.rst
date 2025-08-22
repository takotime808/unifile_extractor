Tutorial: Extracting from a PDF and a URL
========================================

This short tutorial shows how to use **unifile** from Python code
to extract text into the standardized table format.

Extracting from a PDF
---------------------

Save this as ``example_extract.py``:

.. code-block:: python

    import pandas as pd
    from unifile.pipeline import extract_to_table

    # Path to a local PDF file
    df = extract_to_table("sample.pdf")

    print(df.head())

This will return a pandas DataFrame with the standardized schema::

    [source_path, source_name, file_type, unit_type, unit_id,
     content, char_count, metadata, status, error]


Extracting from a URL
---------------------

You can also extract directly from a web page::

.. code-block:: python

    from unifile.pipeline import extract_to_table

    df = extract_to_table("https://www.python.org/")

    print(df.head())
