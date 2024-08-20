import eutil

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
