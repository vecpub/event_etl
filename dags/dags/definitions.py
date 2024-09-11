from dagster import Definitions, load_assets_from_modules
from dagster_dbt import DbtCliResource
#from .assets import event_etl_dbt_assets
from .project import event_etl_project
from .schedules import schedules

from . import assets
all_assets = load_assets_from_modules([assets])

defs = Definitions(
    #assets=[event_etl_dbt_assets],
    assets = all_assets,
    schedules=schedules,
    resources={
        "dbt": DbtCliResource(project_dir=event_etl_project),
    },
)