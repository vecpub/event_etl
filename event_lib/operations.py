import json
import time
from tqdm import tqdm
from eutil import ChatModel, execute_query


class Slice():
    """Provides a dataframe based on preset queries or custom query."""
    def __init__(self, slice_name=None, query=None):
        self.query=query
        if slice_name:
            self.query = self.get_slice_query(slice_name)
        self.df = execute_query(self.query)

    def get_slice_query(self, slice_name):
        query_bank = {'place_event':
        """select
                event.name as event_name,
                place.name as location_name,
                date(min(start_datetime))::varchar as start_date,
                count(start_datetime) as occurence_count
            from public.event event 
            INNER JOIN public.place place on event.place_key = place.key
            where date(start_datetime) >= current_date
            GROUP BY 1,2
            ORDER BY start_date
            --limit 100 offset 100;"""
        }
        selected_query = query_bank[slice_name]
        return selected_query

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
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": json.dumps(event_json_row)} 
    ]
    response = chat_model.complete(messages)
    return response



#pytest event_lib/operations.py -rP -k test_summarize_event
def test_summarize_event():
    cm = ChatModel('perplexity', store_history=False)
    test_data = {
        'event_name': 'BRIC Celebrate Brooklyn! Festival',
        'location_name': 'Prospect Park Bandshell',
        'start_date': '2024-08-14', 'occurence_count': 1,
        'query': 'What event is playing on start_date?',
        }
    print(summarize_event(test_data, cm))