import gradio as gr
from elasticsearch import Elasticsearch
import elasticsearch

import boto3
import pandas as pd

from esutils import get_index_fields,count_docs
from minioutils import calculate_bucket_size

from minio import Minio

import math

def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])

# Function to handle search queries
def search_query(query,settings,size):
    INDEX_NAME = "objaverse"
    # Initialize ElasticSearch client
    es = Elasticsearch([settings['es_url']], verify_certs=False, basic_auth=(settings['es_user'],settings['es_pass']))

    if settings['fields'] == []:
        default_cols = ["uri","uid","name","publishedAt","user","description","license"]
    else:
        default_cols = settings['fields']

    res = es.search(index=INDEX_NAME, body={"query": {"query_string": {"query":query,"fields":default_cols}}},size=size)
    hits = res['hits']['hits']
    data = []
    for hit in hits:
        source = hit['_source']

        sub_obj = { field:source[field] for field in default_cols if field in source}

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
    settings_state['minio_key'] = minio_access
    settings_state['minio_secret'] = minio_secret


    with open("config.env","w") as file:
        for key,val in settings_state.items():
            if key == "fields" or type(val)==list:
                file.write(f"{key}={val}\n".format(key,"|".join(val)))
            else:
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

def get_es(settings_state):

    try:
        # Initialize ElasticSearch client
        es = Elasticsearch([settings['es_url']],
                       verify_certs=False,
                       basic_auth=(settings['es_user'],settings['es_pass']))
        # Check if the connection is successful
        return es
    except elasticsearch.ConnectionError as e:
        raise gr.Error(f"Error: {e}")    

def get_minio(settings_state):

    # Initialize Minio client

    client = Minio(settings['minio_url'],
                access_key=settings['minio_key'],
                secret_key=settings['minio_secret'],
                secure=False
                )

    return client

def update_df(selectData,settings_state):
    if type(selectData)==list:
        settings_state["fields"]=selectData
    return settings_state

# Create Gradio interface
with gr.Blocks() as demo:
    
    settings = dotenv_values("config.env")
    settings['fields'] = settings['fields'].split("|")
    settings_state = gr.State(settings)


    es = get_es(settings)
    minio_client = get_minio(settings)

    with gr.Tabs():
        with gr.TabItem("Search"):
            with gr.Row():
                with gr.Column(scale=1):
                    # Dropdown for data options
                    dropdown_fields = gr.Dropdown(
                        choices=get_index_fields(es,settings['es_index']),
                        multiselect=True,
                        value=settings['fields'],
                        label="Select Fields"
                    )

                    dropdown_fields.select(fn=update_df,inputs=[dropdown_fields,settings_state],outputs=[settings_state])
                with gr.Column(scale=4):
                    search_input = gr.Textbox(label="Search Query")
                    max_search = gr.Number(value=10,label="Max")
                    search_button = gr.Button("Search")
                    search_results = gr.Dataframe(headers=settings['fields'])
                    search_button.click(fn=search_query, inputs=[search_input,settings_state,max_search], outputs=search_results)

                with gr.Column(scale=1):
                    gr.Number(value=count_docs(es,settings['es_index']),label="Total Objects",interactive=False)
                    total_bytes = calculate_bucket_size(minio_client,settings['minio_bucket'])
                    gr.Text(value=convert_size(total_bytes),label="Total",interactive=False)

        with gr.TabItem("Upload"):
            with gr.Row():
                file_input = gr.File(label="3D File")
                name_input = gr.Textbox(label="Name")
                user_input = gr.Textbox(label="User")
                description_input = gr.Textbox(label="Description")
                screenshot_input = gr.File(label="Renders")
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