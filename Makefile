run_dtl:
	python ./dlt/pl_ticketmaster.py

run_dbt:
	cd dbt; dbt run

write_ui_parquet_files:
	python -c 'import operations; operations.write_ui_parquet_files()'