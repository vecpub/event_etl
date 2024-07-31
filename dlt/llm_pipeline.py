import dlt
import time
import json

from dlt.sources.helpers.rest_client import RESTClient
from dlt.sources.helpers.rest_client.auth import BearerTokenAuth

client = RESTClient(
    base_url="https://api.openai.com/v1",
    headers={"Content-Type": "application/json"},
    #data_selector="choices[0].message.content.domain_names"
)
response = client.post("/chat/completions", 
                      auth=BearerTokenAuth(token=dlt.secrets.get("sources.credentials.openai_api_key")),
                      json={
                          "model": "gpt-4o",
                          "response_format": { "type": "json_object" },
                          "messages": [
                              {"role": "system", "content": "You are a naming assistant that returns JSON that always includes a key called domain_names"},
                              {"role": "user", "content": "List a bunch of domain names that are no more than 6 letters and are catchy"}
                              ]
                            }
)

pipeline = dlt.pipeline(
    pipeline_name="llm_test_pipeline",
    destination="postgres",
    dataset_name="llm_test",
)
print(response.json())

json_response = json.loads(response.json()['choices'][0]['message']['content'])

load_info = pipeline.run(json_response['domain_names'], table_name="llm_test")
row_counts = pipeline.last_trace.last_normalize_info

print(row_counts)
print("------")
print(load_info)

