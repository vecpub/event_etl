from dagster import asset, AssetExecutionContext, op, OpExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets, get_asset_key_for_model

from .project import event_etl_project

import json
import duckdb
import requests
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

from eutil import ChatModel, execute_query, extract_json_from_response, config, midpoint, parse_messy_start_times
from operations import write_parquet_files_to_dev, write_parquet_files_to_s3

schema = config['schema']

@dbt_assets(manifest=event_etl_project.manifest_path)
def event_etl_dbt_assets(context: AssetExecutionContext, dbt: DbtCliResource):
    yield from dbt.cli(["build"], context=context).stream()

@asset(compute_kind='python')
def ingest_direct_web(context: AssetExecutionContext) -> None:
    """
    Refresh based on schedule found in url_source
    """
    sources_to_refresh = execute_query(f"""select * from {schema}.url_source where last_processed < now() - interval '168 hours' or last_processed is null""")
    context.add_output_metadata({"num_rows_refreshed": len(sources_to_refresh)})
    current_date = datetime.now().strftime('%Y-%m-%d')
    cm = ChatModel('openai')
    cm.set_system_prompt(f"""
    You are an event summarizing assistant.
    Please extract event details and return as a JSON array of events.
    Required json fields: 'event_name', 'venue_name', and 'start_date'
    Optional json fields: 'start_time', 'street_address', 'postal_code', 'state_code', 'short_description'
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
        execute_query(f"""
            insert into {schema}.json_dump (source_type, source_name, json_data)
            VALUES(%s, %s, %s)
        """, params=('direct_web', url, json.dumps(parsed_json)))
        execute_query(f"""UPDATE {schema}.url_source set last_processed=now() where url = %s""", params=(url,))

@asset(compute_kind="python")
def ingest_newsletter() -> None:
    pass

@asset(deps=get_asset_key_for_model([event_etl_dbt_assets], "stg_place"))
def extract_place_alias_from_tm() -> None:
    """Refresh ticketmaster provided aliases"""
    execute_query(f"""with tm_source as (
        select distinct
            event._embedded->'venues'->0->>'name' as name,
            md5(concat(
                event._embedded->'venues'->0->>'name', '|' , event._embedded->'venues'->0->'state'->>'stateCode'
            )) as key,
            event._embedded->'venues'->0->'aliases' as aliases
        from pipeline_ticketmaster.stg_ticketmaster event order by 1
        )
        INSERT INTO {schema}.place_alias (place_name, place_key, alias_name)
        select name as place_name, key as place_key, value->>0 as alias_name from tm_source, jsonb_array_elements(aliases) where aliases is not null
        ON CONFLICT (alias_name) DO NOTHING
    """)


@asset(compute_kind="python", deps=[ingest_direct_web, ingest_newsletter])
def place_supplemental(context: AssetExecutionContext) -> None:
    """Match against existing records, lookup in overture data if not available, add all places to places_supplemental
    """
    records = execute_query(f"""
    SELECT json_records->>'venue_name' as venue_name, json_records as json_data
    FROM {schema}.json_dump, jsonb_array_elements(json_data) AS json_records;""")
    unique_places = records['venue_name'].unique()
    unique_place_mapping = {}
    for place in unique_places:
        unique_place_mapping[place] = None

    # 1. Batch match to existing records
    matches_existing = execute_query(f"""
        SELECT key, name FROM (
            SELECT key, name FROM {schema}.place
            UNION select key, name from {schema}.place_supplemental
        ) where name ilike ANY(%s);""",
                        params=([k for k, v in unique_place_mapping.items() if v is None],))

    for _, row in matches_existing.iterrows():
        unique_place_mapping[row['name']] = row['key']

    # 2. Batch match to existing aliases
    matches_alias = execute_query(f"""select place_key, alias_name from {schema}.place_alias where alias_name = ANY(%s);""", 
                        params=([k for k, v in unique_place_mapping.items() if v is None],))

    remaining_items = {k:None for k,v in unique_place_mapping.items() if v is None}

    if remaining_items:
        db = duckdb.connect()
        query = f"""SELECT * FROM read_parquet('{config['nyc_place_parquet_path']}') WHERE name ILIKE ?"""

    for place in remaining_items.keys():
        place_match = db.execute(query, (place,)).df()
        # Currently only matches against exact match with one returned record
        if len(place_match) == 1:
            remaining_items[place] = place_match

    # add places matched in overture to places_supplemental
    found_places = {k:v for k,v in remaining_items.items() if v is not None}
    context.add_output_metadata({
        "total_new_places": len(remaining_items),
        "found_in_overture": len(found_places)
        })

    for place, data in found_places.items():
        key_base = data['name'][0] + '|' + data['region'][0]
        execute_query(f"""
        INSERT INTO {schema}.place_supplemental(
            name, source, key, external_id, lat, lon, street, city_name, state_code, postal_code, website)
            VALUES (%s, %s, md5(%s)::uuid, %s, %s, %s, %s, %s, %s, %s, %s)
        """, params=((
            data['name'][0],
            'overture',
            key_base,
            data['id'][0],
            midpoint(data['bbox'][0])[1],
            midpoint(data['bbox'][0])[0],
            data['street'][0],
            data['locality'][0],
            data['region'][0],
            data['postcode'][0],
            data['websites'][0][0]
        )))

    # add any unmapped places to place_supplemental so events can still be matchec
    missing_places = {k:v for k,v in remaining_items.items() if v is None}
    # Write any unmatched records as 'unassigned'
    for place in missing_places.keys():
        # Get first record only
        rec = records.query("venue_name==@place")['json_data'].iat[0]

        street_address = rec.get('street_address', None)
        state_code = rec.get('state_code', 'NY')
        postal_code = rec.get('postal_code', None)

        key_base = place + '|' + state_code

        execute_query(f"""
        INSERT INTO {schema}.place_supplemental(
            name, source, key, street, state_code, postal_code)
            VALUES (%s, %s, md5(%s)::uuid, %s, %s, %s)
        """, params=((
            place,
            'unassigned',
            key_base,
            street_address,
            state_code,
            postal_code
        )))


@asset(compute_kind="python", deps=[place_supplemental])
def event_supplemental(context: AssetExecutionContext) -> None:
    """Add new event data. Map to places, deduplicate against existing events
    """
    # Pull raw json records
    records = execute_query(f"""
    SELECT
        source_name,
        json_records->>'event_name' as event_name,
        json_records->>'venue_name' as venue_name,
        json_records->>'start_date' as start_date,
        json_records->>'start_time' as start_time
    FROM {schema}.json_dump, jsonb_array_elements(json_data) AS json_records
    WHERE is_processed is null;""")

    context.add_output_metadata({"num_events": len(records)})
    if len(records) == 0:
        return

    unique_events = records['event_name'].unique()
    unique_places = records['venue_name'].unique()

    # Map to existing places - all places should exist due to proccess_places step
    # !This does not correctly handle places with multiple locations (e.g. Ace Hotel)
    matched_places = execute_query(f"""
    SELECT * FROM (
    SELECT key, name FROM {schema}.place
    UNION select key, name from {schema}.place_supplemental
    ) places
    WHERE name = ANY(%s)
    """, params=(list(unique_places),))

    mapped_places = pd.merge(records, matched_places, left_on='venue_name', right_on='name', how='inner')

    # Batch match (Exact match against event names)
    existing_events = execute_query(f"""SELECT * FROM (
    SELECT name as event_name FROM {schema}.event
    UNION select name from {schema}.event_supplemental
    ) events
    WHERE event_name ilike ANY(%s)
    """, params=(list(unique_events),))

    context.add_output_metadata({"duplicate_events": len(existing_events)})

    existing_events['already_exists'] = True
    mapped_events = pd.merge(mapped_places, existing_events, on='event_name', how='left')

    mapped_events['parsed_start_datetime'] = mapped_events.apply(
        lambda row: parse_messy_start_times(row['start_date'], row['start_time']), axis=1
    )

    deduped_events = mapped_events.query("already_exists != True")

    # insert rows
    for _, row in deduped_events.iterrows():
        execute_query(f"""
        INSERT INTO {schema}.event_supplemental(
            name, source, key, start_datetime, place_key)
            VALUES (%s, %s, md5(concat(%s::text,'|',%s::timestamp))::uuid, %s, %s)
            ON CONFLICT (key) DO NOTHING
        """, params=((
            row['event_name'],
            row['source_name'],
            row['event_name'],
            row['parsed_start_datetime'],
            row['parsed_start_datetime'],
            row['key']
        )))

    # mark as processed
    execute_query(f"""UPDATE {schema}.json_dump SET is_processed = true
    WHERE is_processed IS NULL;""")


@asset(compute_kind="python", deps=[
    get_asset_key_for_model([event_etl_dbt_assets], "place"),
    get_asset_key_for_model([event_etl_dbt_assets], "event")
    ])
def dev_parquet_files(context: AssetExecutionContext) -> None:
    write_parquet_files_to_dev()

@asset
def prod_parquet_files(context: AssetExecutionContext) -> None:
    write_parquet_files_to_s3()