from elasticsearch import Elasticsearch

def count_docs(es:Elasticsearch, index_name:str):

    es.indices.refresh(index=index_name)
    res = es.cat.count(index=index_name, params={"format": "json"})

    if len(res)>0:
        return int(res[0]["count"])
    else:
        return 0

def get_index_fields(es:Elasticsearch, index_name:str):
    """
    Retrieves the list of fields from a specified index in Elasticsearch.

    Parameters:
    es_host (str): The Elasticsearch host.
    es_port (int): The Elasticsearch port.
    index_name (str): The name of the index to retrieve fields from.

    Returns:
    list: A list of field names.
    """


    # Get the mapping for the specified index
    try:
        mapping = es.indices.get_mapping(index=index_name)
    except Exception as e:
        print(f"Error retrieving mapping for index {index_name}: {e}")
        return []

    # Extract field names from the mapping
    fields = []
    properties = mapping.get(index_name, {}).get('mappings', {}).get('properties', {})

    def extract_fields(properties, parent_key=''):
        for field, field_props in properties.items():
            full_field = f"{parent_key}.{field}" if parent_key else field
            fields.append(full_field)
            if 'properties' in field_props:
                extract_fields(field_props['properties'], full_field)

    extract_fields(properties)

    return fields
