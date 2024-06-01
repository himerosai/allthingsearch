import gradio as gr
from elasticsearch import Elasticsearch
import boto3
import pandas as pd

# Initialize ElasticSearch client
es = Elasticsearch([{'host': 'localhost', 'port': 9200}])

# Initialize Minio client
minio_client = boto3.client(
    's3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='AKIAIOSFODNN7EXAMPLE',
    aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY',
    region_name='us-east-1',
)


# Function to handle search queries
def search_query(query):
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
    df = pd.DataFrame(data)
    return df


# Function to handle file uploads
def upload_file(file, description, screenshot):
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
def browse_objects():
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


# Create Gradio interface
with gr.Blocks() as demo:
    with gr.Tabs():
        with gr.TabItem("Search"):
            search_input = gr.Textbox(label="Search Query")
            search_button = gr.Button("Search")
            search_results = gr.Dataframe()
            search_button.click(fn=search_query, inputs=search_input, outputs=search_results)

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

# Launch the app
demo.launch()