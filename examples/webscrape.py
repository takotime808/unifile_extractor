# Copyright (c) 2025 takotime808

import asyncio

from unifile.extractors.web_extractor import extract_from_url, extract_many, FetchOptions

opts = FetchOptions(render_js=False, respect_robots=True)
df = asyncio.run(extract_from_url("https://www.python.org", opts=opts))
print(df.head())

urls = ["https://example.com", "https://www.python.org", "https://www.kdedirect.com/collections/uas-multi-rotor-brushless-motors"]
df_many = asyncio.run(extract_many(urls, concurrency=5, per_host_delay=0.5, opts=opts))
output_filepath = "outputs.csv"
df_many.to_csv(output_filepath)
print(f"Outputs from provided urls are stored in {output_filepath}")