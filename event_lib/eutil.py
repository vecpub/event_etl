import os
import yaml
import json
import duckdb
import typing
import psycopg
import pandas as pd
from collections import OrderedDict

from openai import OpenAI

def load_config(path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, path)
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

secrets = load_config('secrets.yaml')
config = load_config('config.yaml')['dev']

def hello():
    print("Hello")

def execute_query(query, connection_string=None, params=None):
    """Returns a df based on a select query or also inserts/updates/deletes. Supports named parameters"""
    if not connection_string:
        creds = secrets['event_db_creds']
        connection_string = f"dbname={creds['database']} user={creds['user']} password={creds['password']} host={creds['host']}"
    with psycopg.connect(connection_string) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            if cur.description:
                records = cur.fetchall()
                column_names = [desc.name for desc in cur.description]
                df = pd.DataFrame(records, columns=column_names)
                return df
            else:
                conn.commit()
                return None


class ChainableResponse:
    """Return response but allow for method chaining"""
    def __init__(self, obj, result):
        self.obj = obj
        self.result = result

    def __getattr__(self, name):
        # If trying to access a method on the wrapped object, return the object itself
        return getattr(self.obj, name)

    def __str__(self):
        return str(self.result)

    def __repr__(self):
        return repr(self.result)

    def __call__(self):
        return self.result

class ChatModel():
    """ ChatModel class to interact with chat providers

    Args:
    provider (str): The chat service provider. Options: 'openai', 'perplexity', 'ollama'
    model (str): The model to use - sane defaults if not provided
    store_history (bool): Store chat history

    Functions:
    complete(messages, tools=None, tool_choice=None): Generate response from chat provider
    """
    def __init__(self, provider, model=None, store_history=False):
        self.provider=provider
        self.model=model or self.get_default_model(provider)
        self.store_history=store_history
        self.client = self.setup_client()
        self.system_message = None
        self.message_history = []
        self.tool_manager = None

    def setup_client(self):
        if self.provider == 'openai':
            return OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        if self.provider == 'perplexity':
            return OpenAI(api_key=os.getenv('PERPLEXITY_KEY'), base_url="https://api.perplexity.ai")
        if self.provider == 'ollama':
            return OpenAI(api_key='unused', base_url='http://localhost:11434/v1')
  
    def get_default_model(self, provider):
        defaults = {
            'openai': 'gpt-4o',
            'perplexity': 'llama-3.1-sonar-small-128k-online',
            'ollama': 'llama3.1'
        }
        return defaults.get(provider)
    
    def set_system_message(self, message):
        self.system_message = {'role': 'system', 'content': message}
        return self
    
    def apply(self, *funcs):
        result = self
        for func in funcs:
            result = func(result)
        return result

    def set_tool_manager(self, tool_manager):
        self.tool_manager = tool_manager
        return self

    def complete(self, messages, tool_choice=None):
        if isinstance(messages, str):
            messages = [{'role':'user', 'content':messages}]

        if self.store_history:
            self.message_history = self.message_history + messages 
        else:
            self.message_history = messages
        
        if self.system_message:
            completion_messages = [self.system_message] + self.message_history
        else:
            completion_messages = self.message_history

        tools = self.tool_manager.get_tools() if self.tool_manager else None

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=completion_messages,
                tools=tools,
                tool_choice=tool_choice,
            )
            resp = response.choices[0].message

            if resp.tool_calls:
                # Add tool calls message and response to history
                self.message_history.append({'role':'assistant', 'tool_calls':resp.tool_calls})
                for tool_call in resp.tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    called_tool_response = self.tool_manager.tools[function_name](**json.loads(function_args))
                    self.message_history.append({
                        'role': 'tool',
                        'content': called_tool_response,
                        'tool_call_id': tool_call.id,
                        })
                    tool_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=self.message_history)
                    resp = tool_response.choices[0].message

            self.message_history.append({'role': resp.role , 'content': resp.content})

            return ChainableResponse(self, resp.content)

        except Exception as e:
            print("Unable to generate response")
            print(f'Exception: {e}')
            return e


class Slice():
    """Provides a dataframe based on preset queries or custom query."""
    def __init__(self, slice_name=None, query=None):
        self.query=query or self.get_slice_query(slice_name)
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


def load_duckdb():
    conn = duckdb.connect()
    creds = secrets['event_db_creds']
    conn.sql(f"""
    ATTACH '
        dbname={creds['database']}  
        hostaddr=127.0.0.1 
        user={creds['user']}  
        password={creds['password']}  
        port={5432}
    ' AS db (TYPE postgres, READ_ONLY); 
             """)
    return conn


class ToolManager():
    def __init__(self):
        self.tools = {}
        self.tool_definitions = OrderedDict()

    def add_tool(self, tool_definition, func):
        function_name = tool_definition['function']['name']
        self.tools[function_name] = func
        self.tool_definitions[function_name] = tool_definition

    def get_tools(self):
        return [definition for _, definition in self.tool_definitions.items()]


def tool_builder(
        function_name: str,
        params: dict = None,
        function_desc: str = None,
        param_desc: dict = None,
        parameter_type: str = 'object',
        strict=True,
    ) -> typing.Union[str, dict]:
    '''
    Build an OpenAI tool spec

    Args:
        params (dict, optional): dict mapping names to types
            If a list is provided infers type and uses list as enum

    Returns:
        String or dict based on return_json

    Example:
    tool_builder('set_king', function_desc='Set the king',
                 params={'name': str, 'place': ['Jungle','Moon'], 'years': int},
                 param_desc={'place': 'Where', 'name': 'Who', 'years': 'How long'})
    '''
    function_obj = {'name': function_name, 'strict': strict}
    if function_desc:
        function_obj['desc'] = function_desc
    if strict:
        function_obj['strict'] = strict

    param_obj = {'type': parameter_type, 'properties': {}, 'additionalProperties': False}

    if params:
        #required not implemented in OpenAI spec - takes all params
        param_obj['required'] = [param for param, _ in params.items()]
    # All functions need 'additionalProperties': False even if no params
    function_obj['parameters'] = param_obj

    if params:
        #pytypes to json types
        type_mapping = {str: 'string',int: 'integer',float: 'number',bool: 'boolean',list: 'array',dict: 'object'}
        for param, pytype in params.items():

            if isinstance(pytype, list):
                param_obj['properties'][param] = {
                    'type': type_mapping.get(type(pytype[0]),'unkown'),
                    'enum': pytype
                }
            else:
                param_obj['properties'][param] = {'type': type_mapping.get(pytype)}

    if param_desc:
        for param, desc in param_desc.items():
            param_obj['properties'][param]['description'] = desc

    tool_spec = {'type': 'function', 'function': function_obj}

    return tool_spec


#pytest event_lib/eutil.py -rP -k test_complete_with_string_no_history
def test_complete_with_string_no_history():
    cm = ChatModel('openai', store_history=False)
    print('no message history, string input')
    print(cm.complete("What is the capital of France?"))

def test_complete_with_string_and_history():
    cm = ChatModel('openai', store_history=True)
    print('message history, string input')
    print(cm.complete("What is the capital of France?"))
    print(cm.complete("Repeat the conversation so far"))

def test_complete_with_multiple_messages():
    print('no message history, system message input')
    cm = ChatModel('openai', store_history=False)
    messages = [
        {"role": "system", "content": 'Turn everyting into baby talk'},
        {"role": "user", "content": 'What is the capital of France?'}
    ]
    print(cm.complete(messages))

def test_complete_with_multiple_messages_and_history():
    print('message history, system message input')
    cm = ChatModel('ollama', store_history=True)
    messages = [
        {"role": "system", "content": 'Turn everyting into baby talk'},
        {"role": "user", "content": 'What is the capital of France?'}
    ]
    print(cm.complete(messages))
    print(cm.complete("Can you repeat the conversation so far as a pirate?"))


def test_config():
    print(config['ui_app_path'])
