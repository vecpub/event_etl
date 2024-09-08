run_etl_dev: run_dbt write_parquet_to_dev

run_etl_prod: run_dlt run_dbt write_parquet_to_prod

run_dlt:
	python ./dlt/pl_ticketmaster.py

run_dbt:
	cd dbt; dbt run

write_parquet_to_dev:
	python -c 'import operations; operations.write_parquet_files_to_dev()'

write_parquet_to_prod:
	python -c 'import operations; operations.write_parquet_files_to_s3()'
