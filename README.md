# Event ETL

ETL pipeline for NYC event data: from APIs and web sources to Parquet files served in a Svelte app.

- Ingests event and venue data from Ticketmaster, web scrapes, Overture Maps, and LLM APIs. 
- Data staged in PostgreSQL, transformed with dbt, and enriched via supplemental tables and deduplication steps. 
- Final event/place models are exported as Parquet files (local or S3) and consumed by a Svelte web application using DuckDB WASM.