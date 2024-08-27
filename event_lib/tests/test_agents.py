from agents.dossier import Dossier

def test_dossier_tools():
    dos = Dossier('Test Topic')
    dos.set_chat_model()
    tool_names = [t['function']['name'] for t in dos.cm.tool_manager.get_tools() or []] 
    assert 'search_web' in tool_names


