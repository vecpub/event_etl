import dlt
import time
from dlt.sources.helpers.rest_client import paginate
from dlt.sources.helpers.rest_client import RESTClient
from dlt.sources.helpers.rest_client.paginators import OffsetPaginator

'''
# https://data.cityofnewyork.us/City-Government/NYC-Permitted-Event-Information/tvpp-9vvx/about_data
'''

client = RESTClient(
    base_url="https://data.cityofnewyork.us/resource",
    paginator=OffsetPaginator(
        limit=1000,
        limit_param="$limit",
        offset_param="$offset",
        total_path=None,
        maximum_offset=5000,
    )
)

@dlt.resource(table_name='permitted_events', write_disposition='merge', primary_key=('event_id', 'start_date_time'))
def load_permit_data(
    updated_at=dlt.sources.incremental("event_id", initial_value="0")
):
    for page in client.paginate('/tvpp-9vvx.json',params={
            "$where": f'event_id > {updated_at.last_value}',
            "$order": "event_id%20ASC",
        },
    ):
        time.sleep(0.5)
        yield page

pipeline = dlt.pipeline(
    pipeline_name="permitted_events_pipeline",
    destination="postgres",
    dataset_name="permitted_events",
    #dev_mode=True,
)
load_info = pipeline.run(load_permit_data)
row_counts = pipeline.last_trace.last_normalize_info

print(row_counts)
print("------")
print(load_info)




