import gradio as gr
from elasticsearch import Elasticsearch
import elasticsearch

import boto3
import pandas as pd

# Function to handle search queries
def search_query(query,settings):
    INDEX_NAME = "objaverse"
    # Initialize ElasticSearch client
    es = Elasticsearch([settings['es_url']], verify_certs=False, basic_auth=(settings['es_user'],settings['es_pass']))
    default_cols = ["uri","uid","name","publishedAt","user","description","license"]
    res = es.search(index=INDEX_NAME, body={"query": {"match": {"description": query}}})
    hits = res['hits']['hits']
    data = []
    for hit in hits:
        source = hit['_source']

        sub_obj = { field:source[field] for field in default_cols}

        data.append(sub_obj)

    if len(data)==0:
        empty = { field:[] for field in default_cols}
        df = pd.DataFrame(empty)
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
            file.write(f"{key}={val}\n".format(key,val))

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


from dotenv import dotenv_values

# Create Gradio interface
with gr.Blocks() as demo:
    
    settings = dotenv_values("config.env")
    settings_state = gr.State(settings)

    with gr.Tabs():
        with gr.TabItem("Search"):
            with gr.Row():
                with gr.Column(scale=0):
                    gr.Markdown(
                    """
                    Fields:
                    * A
                    * B
                    """)
                with gr.Column(scale=1):
                    search_input = gr.Textbox(label="Search Query")
                    search_button = gr.Button("Search")
                    search_results = gr.Dataframe()
                    search_button.click(fn=search_query, inputs=[search_input,settings_state], outputs=search_results)

                with gr.Column(scale=0):
                    gr.Textbox(
                    """
                    Total Objects:100
                    """)

        with gr.TabItem("Upload"):
            with gr.Row():
                file_input = gr.File(label="3D File")
                description_input = gr.Textbox(label="Description")
                screenshot_input = gr.File(label="Screenshot (optional)")
                upload_button = gr.Button("Upload")
                upload_result = gr.Textbox(label="Result")
                upload_button.click(fn=upload_file, inputs=[file_input, description_input, screenshot_input],
                                    outputs=upload_result)

        with gr.TabItem("Browse"):
            with gr.Row():
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
demo.launch(share=True)