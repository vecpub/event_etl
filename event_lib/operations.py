import re
import json
import time
import json
from tqdm import tqdm
from eutil import config, ChatModel, Slice, execute_query, load_duckdb, extract_json_from_response

import logging

logging.basicConfig(
    level=logging.INFO,  # Default logging level
    #format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


'''
Deduplicate Places
Uses perplexity to identify the 'least accurate' record when a record has multiple places.
High success rate but stochastic.
Next steps are easy way to flag data (possibly from front end) to review and revise results
Retry logic is also needed
USAGE: ipython; import operations; operations.run_deduplicate_places()
'''

def setup_deduplicate_places():
    execute_query("CREATE TABLE IF NOT EXISTS public.place_is_deleted (row_hash uuid)")

def run_deduplicate_places():
    """ Find all records with same place_id and duplicate row data hash"""
    duplicate_places = execute_query("""
        select * from stg_place where key in
        (select key from
        stg_place
        where row_hash not in (select * from public.place_is_deleted)
        group by 1
        having count(row_hash) > 1)
    """)
    logger.info(f'Running deduplicate_places. Duplicate records found: {len(duplicate_places)}')
    duplicate_places['row_hash'] = duplicate_places['row_hash'].apply(lambda x: str(x))
    for key in duplicate_places['key'].unique():
        dup_df = duplicate_places.query('key == @key').copy()
        dup_json = dup_df.to_json(orient='records')
        run_deduplicate_place(dup_json)
    pass

def run_deduplicate_place(dup_json):
    """ """
    cm = ChatModel('perplexity')
    #system_prompt = "Return json containing only the row_hash of the record that represents the record that is least accurate"
    system_prompt = "Return json containing only the row_hash of the record that represents the record that is least accurate. Use web search to validate lat/lon data if needed"

    cm.set_system_prompt(system_prompt)
    llm_result = cm.complete(dup_json)
    parsed_json = extract_json_from_response(llm_result)
    if len(parsed_json['row_hash']) == 36: # Len of uuid
        provided_result = parsed_json['row_hash']
        print(provided_result)
        logger.info(f'Inserting {provided_result} into place_is_deleted table')
        execute_query("""INSERT INTO public.place_is_deleted VALUES (%s)""", params=(provided_result,))
    else:
        print('problems with result format')



'''
Populate Event Place Description
Uses perplexity and web results to summarize an event

python operations.py -c 'run_populate_event_place_desciption()'
'''

def setup_populate_event_place_description():
    execute_query("""CREATE TABLE IF NOT EXISTS public.event_place_description (
        event_name TEXT,
        place_name TEXT,
        description TEXT
    )""")

def run_populate_event_place_desciption():
    '''populates event_place_description table for any blank values'''
    event_place_slice = Slice('place_event')
    cm = ChatModel('perplexity', store_history=False)

    event_json_list = []
    for e in json.loads(event_place_slice.df.to_json(orient='records')):
        event_json_list.append(e)

    for event in tqdm(event_json_list):
        if event_place_description_exists(event['event_name'], event['location_name']) == 0:
            result = summarize_event(event, chat_model=cm)
            print(f'event_name: {event['event_name']}')
            print(f'location_name: {event['location_name']}')
            print(f'result: {result}')
            execute_query("""
            INSERT INTO public.event_place_description 
            (event_name, place_name, description)
            VALUES ( %s, %s, %s )""", params=(
                event['event_name'],event['location_name'],
                result))
            time.sleep(1)

def event_place_description_exists(event_name, event_place):
    return execute_query("""select count(1) from public.event_place_description 
    where event_name = %s and place_name = %s;""", 
    params=(event_name, event_place)).iloc[0]['count']

def summarize_event(event_json_row, chat_model: ChatModel):
    '''Summarize event information - used with perplexity model'''
    system_message = """You are a research assistant ai who uses search to provide thorough factual answers.
    When given a piece of JSON representing an event you will return additional notable information on the event or notable facts about the specific act.
    Answer in natural text and do not repeat the input JSON."""
    chat_model.set_system_prompt(system_message)
    messages = [
        {"role": "user", "content": json.dumps(event_json_row)} 
    ]
    response = str(chat_model.complete(messages))
    return response

def write_ui_parquet_files():
    db = load_duckdb()
    #db.sql("SELECT * FROM db.public.place").to_parquet('/Users/aplucche/repos/svelte-experiments/static/placetest.parquet')
    db.sql(f"copy db.public.place to '{config['ui_app_path']}/place.parquet' (FORMAT PARQUET);")
    db.sql(f"copy db.public.event to '{config['ui_app_path']}/event.parquet' (FORMAT PARQUET);")
    print('files written')
    



