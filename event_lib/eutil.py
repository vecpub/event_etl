import os
import yaml
import json
import psycopg
import pandas as pd
from openai import OpenAI

def get_config_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(script_dir, 'config.yaml')
    return config_path

def load_config():
    config_path = get_config_path()
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

config = load_config()

def hello():
    print("Hello")

def execute_query(query, connection_string=None, params=None):
    """Returns a df based on a select query or also inserts/updates/deletes. Supports named parameters"""
    if not connection_string:
        creds = config['event_db_config']
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
    def __init__(self, provider, model=None, store_history=True):
        self.provider=provider
        self.model=model
        self.store_history=store_history
        self.client = self.setup_client()
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

    def complete(self, messages, tools=None, tool_choice=None):
        if isinstance(messages, str):
            messages = {'role':'user', 'content':messages}
        if self.store_history:
            self.message_history.append(messages)
        else:
            self.message_history = [messages]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=self.message_history,
                tools=tools,
                tool_choice=tool_choice,
            )
            self.message_history.append(response.choices[0].message)
            return response.choices[0].message.content
        except Exception as e:
            print("Unable to generate response")
            print(f'Exception: {e}')
            return e