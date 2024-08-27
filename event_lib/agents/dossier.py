import typing
from datetime import datetime
from dataclasses import dataclass, field
from eutil import ChatModel, ToolManager, infer_tool_spec

import logging
logger = logging.getLogger(__name__)

class Dossier():
    """ Research agent that builds a document on a given topic

    Args:
        research_topic (str): The topic of the document
        call_limit (int): Number of calls to the chat provider allowed
        topics (list): List of document topics - default ['Headline', 'Executive Summary', 'Details', 'Next Steps']
    """
    def __init__(self, research_topic: str, call_limit: int = 5, topics: list=None):
        self.research_topic = research_topic
        self.call_limit = call_limit
        self.topics = topics if topics else ['Headline', 'Executive Summary', 'Details', 'Next Steps']

        self.cm = None
        self.document = {}

        for topic in self.topics:
            self.document[topic] = None

        self.history = []

    def set_chat_model(self):
        """Set chat model and add any functions that will be used as tools"""
        cm = ChatModel('openai', model='gpt-4o-mini', store_history=False)
        tm = ToolManager()

        tm.add_tool(self.search_web, infer_tool_spec('search_web', self.search_web))
        tm.add_tool(self.replace_document_section, infer_tool_spec('replace_document_section', self.replace_document_section))
        tm.add_tool(self.append_document_section, infer_tool_spec('append_document_section', self.append_document_section))

        cm.set_tool_manager(tm)
        self.cm = cm

    def run(self, prompt, tool_choice='auto'):
        self.set_system_prompt()
        if self.call_limit > 0:
            logger.info(f'call limit: {self.call_limit}')
            response = str(self.cm.complete(prompt, tool_choice=tool_choice))
            logger.debug(response)
            self.history.append(response)
        else:
            raise('call limit reached')

    def set_system_prompt(self):
        prompt_template = f'''
        Current Date: {datetime.now().strftime('%Y-%m-%d')}
        You are a research assistant - you are building a document on the topic: {self.research_topic}
        Be specific and do not respond with overly general answers - this research must be actionable!
        The document consists of the following sections:
            {'\n'.join(self.topics)}

        Tools Available:
            search_web: Get summarized web results
            modify_document_section: Replace one of the sections of the document with new text

        You have {self.call_limit} more searches left to improve the document if needed

        The Next Steps section is to guide you
        Only include text in Next Steps that can be achieved with internet research
        Act on these steps if there are searches left
        
        Document Current State:
        {self.document}
        '''
        self.system_prompt = prompt_template
        self.cm.set_system_prompt(prompt_template)

    def search_web(self, search_string: str):
        """
        Searches the web and returns summarized text of results

        Args:
            search_string (str): the search string that will be used
        """
        if self.call_limit > 0:
            self.call_limit -= 1
            print(f'call limit: {self.call_limit}')
            perplexity_cm = ChatModel('perplexity', store_history=False)
            response = str(perplexity_cm.complete(search_string))
            self.history.append(response)
            return response
        else:
            raise('call limit reached')

    def replace_document_section(self, section_name: str, new_section_contents: str):
        """
        Replaces one of the sections in the document with new text

        Args:
            section_name (str): one of the provided section names
            new_section_contents (str): New section contents - will replace old contents
        """
        self.document[section_name] = new_section_contents
        self.set_system_prompt()
        return f'{section_name} updated'

    def append_document_section(self, section_name: str, new_text: str):
        """
        Adds to the end of one of the sections in the document

        Args:
            section_name (str): one of the provided section names
            new_text (str): Text to append to section
        """
        self.document[section_name] = self.document[section_name] or '' + new_text
        self.set_system_prompt()
        return f'{section_name} updated'