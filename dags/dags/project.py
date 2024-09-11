from pathlib import Path

from dagster_dbt import DbtProject

event_etl_project = DbtProject(
    project_dir=Path(__file__).joinpath("..", "..", "..", "dbt").resolve(),
    packaged_project_dir=Path(__file__).joinpath("..", "..", "dbt-project").resolve(),
)
event_etl_project.prepare_if_dev()