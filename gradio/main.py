import gradio as gr
from elasticsearch import Elasticsearch
import elasticsearch

import boto3
import pandas as pd

from esutils import get_index_fields,count_docs
from minioutils import calculate_bucket_size

from minio import Minio

import math

from celery import Celery
import urllib3

urllib3.disable_warnings()

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

    res = es.search(index=INDEX_NAME, body={"query": {"query_string": {"query":query,"fields":default_cols}},"size":size})
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
def upload_file(file_input, user_input,name_input,description_input, manual_input,settings):
    import pathlib
    import hashlib
    import datetime
    import os

    d = datetime.datetime.now()

    es_client = get_es(settings)
    minio_client = get_minio(settings)

    if file_input and os.path.isfile(file_input.name):
        path = file_input.name
        print("Loading file from %s" % path)
        try:

            #lo cal utc ftime
            tz = datetime.timezone.utc
            ft = "%Y-%m-%dT%H:%M:%S"
            t = datetime.datetime.now(tz=tz).strftime(ft)

            upload_info ={"name":name_input,"user":{"username":user_input},"description":description_input,"publishedAt":t}
            print("Upload info %s" % upload_info)

            res = es_client.index(index=settings['es_index'], body=upload_info, refresh='true')

            print("Added upload file object: %s" % res.body['_id'])

            uid = hashlib.md5(open(path,'rb').read()).hexdigest()

            ext = pathlib.Path(path).suffix
    
            print("Adding to Minio with uid %s" % uid)
            # add into minio
            resultio = minio_client.fput_object(
                bucket_name=settings['minio_bucket'], 
                object_name=uid, 
                file_path=path,
                metadata={"es_id" : res.body['_id'],"ext":ext,"status":"uploaded"}
            )

            info =  "created {0} object; etag: {1}, version-id: {2}".format(resultio.object_name, resultio.etag, resultio.version_id)
            return info

        except elasticsearch.ElasticsearchWarning as wan:
            return str(wan)            
        return "Upload successful!"
    else:
        return "No file provided"


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

def get_es(settings):

    try:
        # Initialize ElasticSearch client
        es = Elasticsearch([settings['es_url']],
                       verify_certs=False,
                       basic_auth=(settings['es_user'],settings['es_pass']))
        # Create an empty index just in case
        if es.indices.exists(index=settings['es_index']):
            return es
        else:
            es.indices.create(index=settings['es_index'], ignore=400)
            return es

    except elasticsearch.ConnectionError as e:
        raise gr.Error(f"Error: {e}")    

def get_minio(settings):

    # Initialize Minio client

    client = Minio(settings['minio_url'],
                access_key=settings['minio_key'],
                secret_key=settings['minio_secret'],
                secure=False
                )

    # Make the bucket if it doesn't exist.
    found = client.bucket_exists(settings['minio_bucket'])
    if not found:
        client.make_bucket(settings['minio_bucket'])
        print("Created bucket", settings['minio_bucket'])
    else:
        # TODO: delete the entire bucket also ...
        print("Bucket", settings['minio_bucket'], "already exists")

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

    app = Celery('allthings', broker=settings['redis_url'])

    app.conf.result_backend = settings['redis_url']


    @app.task
    def demo_start():
        return 'Gradio App starting...'


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
                    if total_bytes is None:
                        gr.Text(value="buckt is empty", label="Total", interactive=False)
                    else:
                        gr.Text(value=convert_size(total_bytes),label="Total",interactive=False)

        with gr.TabItem("Upload"):
            with gr.Row():
                file_input = gr.File(label="3D File")
                name_input = gr.Textbox(label="Name")

                description_input = gr.Textbox(label="Description")
                manual_input = gr.File(label="Renders")

                user_input = gr.Dropdown(
                    choices=["admin"],
                    multiselect=False,
                    value="admin",
                    label="User"
                )

                upload_button = gr.Button("Upload")

                upload_result = gr.Textbox(label="Result")

                upload_button.click(fn=upload_file, inputs=[file_input, user_input,name_input,description_input, manual_input,settings_state],
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