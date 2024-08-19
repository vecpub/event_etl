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
