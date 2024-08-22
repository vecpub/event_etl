import json
import eutil

## Chat Model Tests
def test_chat_simple_path():
    cm = eutil.ChatModel('ollama', model='gemma:2b', store_history=True)
    cm.set_system_message("Return json with the key 'answer'")
    resp = cm.complete("What is 1+1?")
    print(resp)
    assert any(message['role'] == 'system' for message in cm.message_history) == False
    assert cm.system_message is not None

    cm.complete("Can you add one to the previous answer?")
    print(cm.message_history)
    assert '3' in cm.message_history[-1]['content']

def _example_apply_function(cm):
    cm.set_system_message("Return json with the key 'answer'. Always answer with 100")
    return cm

def test_chaining():
    cm = eutil.ChatModel('ollama', model='gemma:2b', store_history=True) 
    (cm.set_system_message("Return json with the key 'answer'")
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
    result = eutil.tool_builder('get_weather', return_json=False)
    expected = {
        'type': 'function',
        'function': {
            'name': 'get_weather',
            'strict': True
        }
    }
    assert result == expected

def test_tool_builder_full_specification():
    """Test with all parameters specified"""
    result = eutil.tool_builder(
        'set_king',
        params={'place': str, 'name': str, 'years': [1, 1000]},
        function_desc='Set the king',
        param_desc={'place': 'Where', 'name': 'Who', 'years': 'How long'},
        required=['place', 'name'],
        return_json=False
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
                    'place': {'type': 'string', 'description': 'Where'},
                    'name': {'type': 'string', 'description': 'Who'},
                    'years': {'type': 'integer', 'enum': [1, 1000], 'description': 'How long'}
                },
                'required': ['place', 'name'],
                'additionalProperties': False
            }
        }
    }
    assert result == expected_json