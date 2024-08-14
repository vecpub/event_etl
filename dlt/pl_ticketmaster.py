import dlt
import time
import datetime
from datetime import date
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

def build_periods():
    next_month_start = (date.today().replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    following_month_start = (next_month_start.replace(day=1) + datetime.timedelta(days=32)).replace(day=1)
    current_period = f'*,{next_month_start.strftime("%Y-%m-%dT00:00:00")}'
    following_period = f'{next_month_start.strftime("%Y-%m-%dT00:00:00")},{following_month_start.strftime("%Y-%m-%dT00:00:00")}'
    return [current_period, following_period]
    #return [current_period] #TESTING REMOVE

@dlt.resource(
        table_name='stg_ticketmaster',
        write_disposition='merge',
        primary_key='id',
        max_table_nesting=0,
)
def test_events():
    for category in ["music", "comedy", "film"]:
        for period in build_periods():
            for page in client.paginate("/events.json",
                params={
                    "classificationName": category,
                    "dmaId": 345,
                    "size": 200,
                    "localStartDateTime": period,
                },
            ):
                time.sleep(1)
                yield page

@dlt.resource(
        table_name='stg_ticketmaster',
        write_disposition='merge',
        primary_key='id',
        max_table_nesting=0,
)

def test_events_all():
    """Alternate that pulls all events regardless of classification"""
    for page in client.paginate("/events.json",
        params={
            "dmaId": 345,
            "size": 200,
            #"localStartDateTime": '*,2024-08-21T00:00:00',
            "localStartDateTime": '2024-08-28T00:00:00,2024-09-05T00:00:00',
        },
    ):
        time.sleep(1)
        yield page

pipeline = dlt.pipeline(
    pipeline_name='ticketmaster_pipeline',
    destination='postgres',
    dataset_name='pipeline_ticketmaster',
    dev_mode=False,
)

load_info = pipeline.run(test_events)
row_counts = pipeline.last_trace.last_normalize_info

print(row_counts)
print("------")
print(load_info)