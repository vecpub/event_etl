import json
import time
from tqdm import tqdm
from eutil import config, ChatModel, Slice, execute_query, load_duckdb




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
    chat_model.set_system_message(system_message)
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
    



