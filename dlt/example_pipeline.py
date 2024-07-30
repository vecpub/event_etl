import dlt
import time
from dlt.sources.helpers import requests
from dlt.sources.helpers.rest_client import paginate
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth, APIKeyAuth

from dlt.sources.helpers.rest_client import RESTClient
from dlt.sources.helpers.rest_client.paginators import JSONResponsePaginator


client = RESTClient(
    base_url="https://app.ticketmaster.com/discovery/v2",
    auth=APIKeyAuth(name="apikey", api_key=dlt.secrets.get("sources.credentials.ticketmaster_api_key"), location='param'),
    paginator=JSONResponsePaginator(next_url_path="_links.next.href"),
    data_selector="_embedded.events"
)

# valid_classification_names = ["music", "sports", "comedy", "film", "family", "miscellaneous"] #  "arts-theater" is not valid

@dlt.resource(table_name='test_events', write_disposition='merge', primary_key='id')
def test_events():
    for page in client.paginate("/events.json",
        params={
            "classificationName": "music",
            "dmaId": 345,
            "size": 200,
            "localStartDateTime": "*,2024-09-06T00:00:00",
            #"localStartDateTime": "2024-09-01T00:00:00,2024-10-01T00:00:00",
        },
    ):
        time.sleep(0.5)
        yield page

pipeline = dlt.pipeline(
    pipeline_name='test_ticketmaster',
    destination='postgres',
    dataset_name='event_dev_test',
)

load_info = pipeline.run(test_events)
row_counts = pipeline.last_trace.last_normalize_info

print(row_counts)
print("------")
print(load_info)