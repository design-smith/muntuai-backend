from composio_openai import ComposioToolSet, App
from openai import OpenAI

openai_client = OpenAI()
composio_toolset = ComposioToolSet(entity_id="default")

tools = composio_toolset.get_tools(apps=[App.GMAIL])

print(tools)