import json
import eutil
import typing
import logging

from dataclasses import dataclass

## Chat Model Tests
def test_chat_simple_path():
    cm = eutil.ChatModel('ollama', model='gemma:2b', store_history=True)
    cm.set_system_prompt("Return json with the key 'answer'")
    resp = cm.complete("What is 1+1?")
    print(resp)
    assert any(message['role'] == 'system' for message in cm.message_history) == False
    assert cm.system_message is not None

    cm.complete("Can you add one to the previous answer?")
    print(cm.message_history)
    assert '3' in cm.message_history[-1]['content']

def _example_apply_function(cm):
    cm.set_system_prompt("Return json with the key 'answer'. Always answer with 100")
    return cm

def test_chaining():
    cm = eutil.ChatModel('ollama', model='gemma:2b', store_history=True) 
    (cm.set_system_prompt("Return json with the key 'answer'")
     .complete("What is 1+1?")
     .complete("Can you add one to the previous answer?")
    )
    print(cm.message_history)
    assert '3' in cm.message_history[-1]['content'] 

    (cm.apply(_example_apply_function, _example_apply_function)
     .complete("What is another number?")
     .complete("What is yet another number?")
    )
    print(cm.system_message)
    print(cm.message_history)
    assert cm.system_message['content'] == "Return json with the key 'answer'. Always answer with 100"

def test_get_slice_query():
    slice = eutil.Slice('place_event')
    print(slice.df.head())
    assert len(slice.df) > 0

## Tool Builder Tests
def test_simple_tool_builder():
    """Test basic functionality with minimal inputs."""
    result = eutil.tool_builder('get_weather')
    expected = {
        'type': 'function',
        'function': {
            'name': 'get_weather',
            'strict': True,
            'parameters': {'type': 'object', 'properties': {}, 'additionalProperties': False}
        }
    }
    print(expected)
    print(result)
    assert result == expected

def test_tool_builder_full_specification():
    """Test with all parameters specified"""
    result = eutil.tool_builder(
        'set_king',
        function_desc='Set the king',
        params={'name': str, 'place': ['Jungle','Moon'], 'years': int},
        param_desc={'place': 'Where', 'name': 'Who', 'years': 'How long'},
    )
    expected_json = {
        'type': 'function',
        'function': {
            'name': 'set_king',
            'desc': 'Set the king',
            'strict': True,
            'parameters': {
                'type': 'object',
                'properties': {
                    'name': {'type': 'string', 'description': 'Who'},
                    'place': {'type': 'string', 'enum': ['Jungle', 'Moon'], 'description': 'Where'},
                    'years': {'type': 'integer', 'description': 'How long'}
                },
                'required': ['name', 'place', 'years'],
                'additionalProperties': False
            }
        }
    }
    assert result == expected_json


@dataclass
class King:
    name: str = None
    place: str = None
    years: str = None

    def set_king(self, name: str, place: str=None, years: int=None):
        """Set the king

        Args:
            name (str): Who
            place (str): Where
            years (int): How long
        """
        self.name = name
        self.place = place
        self.years = years
        return f'King set to Name: {self.name}, Place: {self.place}, Years: {self.years}'

    def get_king(self):
        return f'Name: {self.name}, Place: {self.place}, Years: {self.years}'


def test_chat_model_and_tool_manager_integration():
    cm = eutil.ChatModel('openai', model='gpt-4o-mini', store_history=True)
    tm = eutil.ToolManager()

    king = King()
    king.set_king(name='Kong', place='Jungle', years=50)

    tool1 = eutil.tool_builder('set_king', function_desc='Set the king',
                    params={'name':str, 'place':['Jungle', 'Moon'], 'years':int},
                    param_desc={'name':'Who', 'place':'Where', 'years':'How long'},
                    )

    tool2 = eutil.tool_builder('get_king', function_desc='Get the king')

    tm.add_tool(king.set_king, tool1)
    tm.add_tool(king.get_king, tool2)

    cm.set_tool_manager(tm)
    resp = str(cm.complete("Who is the king?"))

    assert 'Kong' in resp

def test_docstring_parser():
    tests = [{
        'docstring':"function desc\n\n    Args:\n        name (str): name desc\n        var1 (int): var1 desc\n\n    Returns:\n        Something",
        'expected': ('function desc', {'name': 'name desc', 'var1': 'var1 desc'})
    },
    {
        'docstring':"function desc\n\n    Args:\n        name: name desc\n        var1: var1 desc\n\n    Returns:\n        Something",
        'expected': ('function desc', {'name': 'name desc', 'var1': 'var1 desc'})
    },
        {
        'docstring':"function desc",
        'expected': ('function desc', {})
    },
    ]

    for test in tests:
        result = eutil.extract_docstring_info(test['docstring'])
        assert result == test['expected']

def test_tool_function_parser():
    king = King()
    built_tool = eutil.tool_builder('set_king', function_desc='Set the king',
                params={'name':str, 'place':['Jungle', 'Moon'], 'years':int},
                param_desc={'name':'Who', 'place':'Where', 'years':'How long'},
                )
    inferred_tool = eutil.infer_tool_spec('set_king', king.set_king, enum_override={'place':['Jungle', 'Moon']})
    assert built_tool == inferred_tool

def test_call_counter():
    cm = eutil.ChatModel('ollama', model='gemma:2b', store_history=True)
    cm.complete("What is 1+1?").complete("What is the capital of France?")
    assert cm.call_count == 2