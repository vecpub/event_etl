from dagster import asset, AssetExecutionContext, op, OpExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

from .project import event_etl_project

import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from eutil import ChatModel, execute_query, extract_json_from_response


@dbt_assets(manifest=event_etl_project.manifest_path)
def event_etl_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()


@asset(compute_kind='python')
def ingest_direct_web(context: AssetExecutionContext) -> None:
    """
    Refresh based on schedule found in url_source
    """
    sources_to_refresh = execute_query("""select * from public.url_source where last_processed < now() - interval '168 hours' or last_processed is null""")
    context.add_output_metadata({"num_rows_refreshed": len(sources_to_refresh)})
    current_date = datetime.now().strftime('%Y-%m-%d')
    cm = ChatModel('openai')
    cm.set_system_prompt(f"""
    You are an event summarizing assistant.
    Please extract event details and return as JSON.
    Include json fields 'event_name', 'venue_name', and 'start_date'.
    Current Date: {current_date}
    """)

    for i, row in sources_to_refresh.iterrows():
        url = row['url']
        context.log.info(f'refreshing {url}')
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers)
        soup = BeautifulSoup(resp.text, 'html.parser')
        txt_resp = soup.get_text()
        completion = cm.complete(txt_resp)
        parsed_json = extract_json_from_response(completion)
        execute_query("""
            insert into public.json_dump (source_type, source_name, json_data)
            VALUES(%s, %s, %s)
        """, params=('direct_web', url, json.dumps(parsed_json)))
        execute_query("""UPDATE public.url_source set last_processed=now() where url = %s""", params=(url,))





@asset(compute_kind="python")
def ingest_newsletter() -> None:
    pass

@asset(compute_kind="python")
def ingest_perplexity_output() -> None:
    pass

@asset(compute_kind="python", deps=[ingest_newsletter, ingest_perplexity_output, ingest_direct_web])
def process_places() -> None:
    pass

@asset(compute_kind="python", deps=[ingest_newsletter, ingest_perplexity_output, ingest_direct_web])
def process_events() -> None:
    pass

@
def check_places() -> None:
    """Check if place exists, lookup place, then record linkage
    Apply on batch of json records
    """
    pass