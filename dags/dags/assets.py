from dagster import asset, AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

from .project import event_etl_project


@dbt_assets(manifest=event_etl_project.manifest_path)
def event_etl_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()

@asset(compute_kind="python")
def something_upstream() -> None:
    print('upstream asset')