import os
import re
import yaml
import json
import duckdb
import typing
import logging
import inspect
import psycopg
import pandas as pd
from collections import OrderedDict

from openai import OpenAI

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def load_config(path):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, path)
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

secrets = load_config('secrets.yaml')
config = load_config('config.yaml')['dev']


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
        logger.debug(f'Returning object')
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
        self.call_count = 0

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
    
    def set_system_prompt(self, message):
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

    def get_tool_manager(self):
        return self.tool_manager

    def complete(self, messages, tool_choice=None, force_content_response=False):
        if self.tool_manager and not tool_choice:
            tool_choice = 'auto'

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

        logger.debug(f'''
    Model: {self.model}
    Call Count: {self.call_count + 1}
    Tools: {[x['function']['name'] for x in tools or []]} Tool Choice: {tool_choice}
    Messages:
    {'\n    '.join(str(x) for x in messages)}
    ''')

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=completion_messages,
                tools=tools,
                tool_choice=tool_choice,
            )

            self.call_count += 1
            resp = response.choices[0].message

            if resp.tool_calls:
                # Add tool calls message and response to history
                self.message_history.append({'role':'assistant', 'tool_calls':resp.tool_calls, 'content':resp.content or None})
                for tool_call in resp.tool_calls:
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    logger.info(f'Calling tool: {function_name} with args: {function_args} \n')
                    called_tool_response = self.tool_manager.tools[function_name](**json.loads(function_args))

                    function_resolution_message = {
                        'role': 'tool',
                        'content': called_tool_response,
                        'tool_call_id': tool_call.id,
                        }
                    self.message_history.append(function_resolution_message)

                tool_response = self.complete(
                    self.message_history,
                    tool_choice=tool_choice,
                    force_content_response=True
                )

                return ChainableResponse(self, tool_response)

            self.message_history.append({'role': resp.role , 'content': resp.content})

            # For recursive tool call do not return self
            if force_content_response:
                return resp.content

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

    def add_tool(self, func, tool_definition):
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

def infer_tool_spec(function_name: str, func: typing.Callable, enum_override: typing.Optional[dict]=None):
    """Builds a tool spec from a function and docstring formatted in the google style

    Args:
        function_name (str): Name of the function
        func (typing.Callable): Function to parse
        enum_override (dict, optional): Override for enum types, e.g. {'name': ['John', 'Jane']}
    """

    function_desc, param_desc = extract_docstring_info(func.__doc__)

    params = inspect.getfullargspec(func).annotations

    if enum_override:
        for key in enum_override:
            params[key] = enum_override[key]

    tool_spec = tool_builder(function_name, function_desc=function_desc,
             params=params,
             param_desc=param_desc)

    return tool_spec

def extract_docstring_info(docstring):
    """Parses docstrings in the google style
    Needs double new lines before args
    Type signatures are optional in args

    Args:
        docstring (str): Docstring
    """
    cleaned_docstring = docstring.strip(' """\n')

    # Split the docstring into segments based on double newlines
    segments = re.split(r'\n\s*\n', cleaned_docstring)

    # Extract the main function description
    function_desc = segments[0].strip() if segments else ''

    # Initialize dictionary for parameters
    param_desc = {}

    # Search for Args section and extract parameter descriptions
    for segment in segments:
        if segment.lstrip().startswith('Args:'):
            param_lines = segment.split('\n')[1:]  # Skip the 'Args:' line
            for line in param_lines:
                # Match lines with optional detailed type information
                match = re.match(r'\s*(\w+)(?:\s+\((.*?)\))?:\s+(.+)', line)
                if match:
                    param_name, param_type, description = match.groups()
                    param_desc[param_name] = f"{description.strip()}"

    return function_desc, param_desc



def extract_json_from_response(response_text, as_str=False):
    try:
        extract_json_string = re.findall(r'```(.*?)```', str(response_text).replace('```json', '```'), re.DOTALL)[0].strip()
        if as_str:
            return extract_json_string
        else:
            return json.loads(extract_json_string)
    except Exception as e:
        print(e)
        return None
