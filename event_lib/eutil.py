import os
import yaml
import json
import duckdb
import psycopg
import pandas as pd
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
        self.model=model
        self.store_history=store_history
        self.client = self.setup_client()
        self.system_message = None
        self.message_history = []

    def setup_client(self):
        if self.provider == 'openai':
            if self.model is None:
                self.model = 'gpt-4o'
            return OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        if self.provider == 'perplexity':
            if self.model is None:
                self.model = 'llama-3.1-sonar-small-128k-online'
            return OpenAI(api_key=os.getenv('PERPLEXITY_KEY'), base_url="https://api.perplexity.ai")
        if self.provider == 'ollama':
            if self.model is None:
                self.model = 'llama3.1'
            return OpenAI(api_key='unused', base_url='http://localhost:11434/v1')
    
    def set_system_message(self, message):
        self.system_message = {'role': 'system', 'content': message}

    def complete(self, messages, tools=None, tool_choice=None):
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

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=completion_messages,
                tools=tools,
                tool_choice=tool_choice,
            )
            resp = response.choices[0].message
            self.message_history.append({'role': resp.role , 'content': resp.content})
            return response.choices[0].message.content
        except Exception as e:
            print("Unable to generate response")
            print(f'Exception: {e}')
            return e


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