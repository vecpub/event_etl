run_etl: run_dlt run_dbt write_ui_parquet_files

run_dlt:
	python ./dlt/pl_ticketmaster.py

run_dbt:
	cd dbt; dbt run

write_ui_parquet_files:
	python -c 'import operations; operations.write_ui_parquet_files()'
