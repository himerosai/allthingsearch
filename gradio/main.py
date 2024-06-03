import gradio as gr
from elasticsearch import Elasticsearch
import elasticsearch

import boto3
import pandas as pd

# Function to handle search queries
def search_query(query,settings):

    # Initialize ElasticSearch client
    es = Elasticsearch([settings['es_url']], verify_certs=False, basic_auth=(settings['es_user'],settings['es_pass']))

    res = es.search(index="3d_objects", body={"query": {"match": {"description": query}}})
    hits = res['hits']['hits']
    data = []
    for hit in hits:
        source = hit['_source']
        data.append({
            'Image': source['image_url'],
            'Description': source['description'],
            'Object ID': source['object_id']
        })

    if len(data)==0:
        df = pd.DataFrame({"Image":[],"Description":[],"OID":[]})
    else:
        df = pd.DataFrame(data)
    return df

# Function to handle file uploads
def upload_file(file, description, screenshot,settings):

    # Initialize Minio client
    minio_client = boto3.client(
        's3',
        endpoint_url=settings['minio_url'],
        aws_access_key_id=settings['minio_key'],
        aws_secret_access_key=settings['minio_secret'],
        region_name='us-east-1',
    )

    object_id = file.name
    minio_client.put_object('3d-files', object_id, file, file.size)

    # Upload screenshot if provided
    screenshot_url = ""
    if screenshot:
        screenshot_id = f"{object_id}_screenshot"
        minio_client.put_object('screenshots', screenshot_id, screenshot, screenshot.size)
        screenshot_url = f"http://localhost:9000/screenshots/{screenshot_id}"

    # Store metadata in ElasticSearch
    es.index(index="3d_objects", body={
        'object_id': object_id,
        'description': description,
        'image_url': screenshot_url
    })
    return "Upload successful!"


# Function to handle browsing
def browse_objects(settings):

    # Initialize ElasticSearch client
    es = Elasticsearch([settings['es_url']],
                       verify_certs=False,
                       basic_auth=(settings['es_user'],settings['es_pass']))

    res = es.search(index="3d_objects", body={"query": {"match_all": {}}})
    hits = res['hits']['hits']
    data = []
    for hit in hits:
        source = hit['_source']
        data.append({
            'Object ID': source['object_id'],
            'Description': source['description'],
            'Image URL': source['image_url']
        })
    df = pd.DataFrame(data)
    return df

def save_settings(es_url,es_user,es_pass,minio_url,minio_access,minio_secret,settings_state):
    # try to connect
    settings_state['es_url'] = es_url
    settings_state['es_user'] = es_user
    settings_state['es_pass'] = es_pass

    settings_state['minio_url'] = minio_url
    settings_state['minio_access'] = minio_access
    settings_state['minio_secret'] = minio_secret

    with open("config.env","w") as file:
        for key,val in settings_state.items():
            file.writeline("{key}={val}".format(key,val))

    try:
        es = Elasticsearch(
            [es_url],
            basic_auth=(es_user,es_pass),
            verify_certs=False
        )
        # Check if the connection is successful
        if not es.ping():
            raise gr.Error("Unable to ping elastic search")
        return settings_state
    except elasticsearch.ConnectionError as e:
        raise gr.Error(f"Error: {e}")

    return settings_state


# Create Gradio interface
with gr.Blocks() as demo:
    settings_state = gr.State({"es_url":None})
    with gr.Tabs():
        with gr.TabItem("Search"):
            search_input = gr.Textbox(label="Search Query")
            search_button = gr.Button("Search")
            search_results = gr.Dataframe(headers=["name", "age", "gender"],
            datatype=["str", "number", "str"],
            row_count=5,
            col_count=(3, "fixed"),
                                          interactive=False)
            search_button.click(fn=search_query, inputs=[search_input,settings_state], outputs=search_results)

        with gr.TabItem("Upload"):
            file_input = gr.File(label="3D File")
            description_input = gr.Textbox(label="Description")
            screenshot_input = gr.File(label="Screenshot (optional)")
            upload_button = gr.Button("Upload")
            upload_result = gr.Textbox(label="Result")
            upload_button.click(fn=upload_file, inputs=[file_input, description_input, screenshot_input],
                                outputs=upload_result)

        with gr.TabItem("Browse"):
            browse_button = gr.Button("Browse")
            browse_results = gr.Dataframe()
            browse_button.click(fn=browse_objects, outputs=browse_results)

        with gr.TabItem("Settings"):
            with gr.Row():
                with gr.Column(scale=1):

                    es_url = gr.Textbox(label="ES url connection",value="http://localhost:9200")
                    es_user = gr.Textbox(label="ES user",value="elastic")
                    es_pass = gr.Textbox(label="ES pass",value="changeme")

                with gr.Column(scale=1):
                    minio_url = gr.Textbox(label="Minio url",value="http://localhost:9000")
                    minio_access = gr.Textbox(label="Minio access key",value="AKIAIOSFODNN7EXAMPLE")
                    minio_secret = gr.Textbox(label="Minio secret key",value="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

            save_button = gr.Button("Save...")

            save_button.click(fn=save_settings, inputs=[es_url,es_user,es_pass,minio_url,minio_access,minio_secret,settings_state],
                                outputs=settings_state)

# Launch the app
demo.launch()