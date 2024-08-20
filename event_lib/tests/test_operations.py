import operations
from eutil import ChatModel, Slice



#pytest event_lib/operations.py -rP -k test_summarize_event
def test_summarize_event():
    cm = ChatModel('ollama', model='gemma:2b', store_history=False)
    test_data = {
        'event_name': 'BRIC Celebrate Brooklyn! Festival',
        'location_name': 'Prospect Park Bandshell',
        'start_date': '2024-08-14', 'occurence_count': 1,
        'query': 'What event is playing on start_date?',
        }
    summary = operations.summarize_event(test_data, cm)
    print(summary)
    print(cm.system_message)
    assert summary is not None


