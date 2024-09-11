import duckdb
from eutil import ChatModel, config

def search_web(search_string: str):
    """
    Searches the web and returns summarized text of results

    Args:
        search_string (str): the search string that will be used
    """
    perplexity_cm = ChatModel('perplexity', store_history=False)
    response = perplexity_cm.complete(search_string)
    return response

def nyc_place_search(search_string: str):
    """
    Searches a database of most NYC locations by name. Includes addresses, lat/lon, type, website
    Valid Search Example: 'Brooklyn Museum'
    Invalid Search Example: 'Brooklyn Museum, Brooklyn NY'

    Args:
        search_string (str): search string. Includes a search of name only
    """
    parquet_path = config['nyc_place_parquet_path']
    db = duckdb.connect()
    formatted_search_string = '%'.join(search_string.split(' '))
    result_df = db.sql(f'''SELECT * FROM '{parquet_path}' 
    where name ilike '%{formatted_search_string}%' limit 20''').df()
    result_df['row_id'] = result_df.index
    return result_df.to_json(orient='records')






