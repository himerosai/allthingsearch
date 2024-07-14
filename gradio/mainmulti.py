import gradio as gr
from elasticsearch import Elasticsearch
import elasticsearch
import pandas as pd
from esutils import get_index_fields,count_docs
from minioutils import calculate_bucket_size
from gcputils import predict_custom_trained_model_sample,get_image,download_image,image_to_base64
from minio import Minio
import math
import urllib3
import os
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

urllib3.disable_warnings()

from fastapi import FastAPI

app = FastAPI()

os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


# Function to handle search queries
def search_query(query, settings, size):
    INDEX_NAME = "objaverse"
    # Initialize ElasticSearch client
    es = Elasticsearch([settings['es_url']], verify_certs=False, basic_auth=(settings['es_user'], settings['es_pass']))

    if settings['fields'] == []:
        default_cols = ["uri", "uid", "name", "publishedAt", "user", "description", "license"]
    else:
        default_cols = settings['fields']

    res = es.search(index=INDEX_NAME,
                    body={"query": {"query_string": {"query": query, "fields": default_cols}}, "size": size})
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

settings = dotenv_values("config.env")
# Create Gradio interface
with gr.Blocks() as demo:

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

        with gr.TabItem("Caption"):
            with gr.Row():

                image_input = gr.Image(label="3d Image Render",type="filepath",sources=["upload","clipboard"])
                object_input = gr.Text(label="Object ID")

                caption = gr.Text(label="Captions")
                caption_qa = gr.Text(label="QA captions")

                gen_button = gr.Button("Generate Image Captions")
                def gen_captions(image_input):
                    LOCATION = settings["gcp_location"]
                    ENDPOINT_ID = settings["endpoint_id"]
                    ENDPOINT_VAQ_ID = settings["endpoint_vaq_id"]
                    PROJECT_ID = settings["project_id"]
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings["gcp_svc_json"]

                    if image_input and os.path.isfile(image_input):
                        print("Loading image from %s" % image_input)

                        image = get_image(image_input)

                        instances = [
                            {"image": image_to_base64(image)},
                        ]

                        captions = predict_custom_trained_model_sample(PROJECT_ID, ENDPOINT_ID, instances, LOCATION)

                        wqa_captions = "\n".join(captions)

                        instances = [
                            {"image": image_to_base64(image), "text": settings["prompt_text"]},
                        ]

                        vqa_captions = predict_custom_trained_model_sample(PROJECT_ID, ENDPOINT_VAQ_ID, instances, LOCATION)

                        qa_captions = "\n".join(vqa_captions)


                        return wqa_captions,qa_captions

                gen_button.click(fn=gen_captions,inputs=[image_input],outputs=[caption,caption_qa])

        with gr.TabItem("Settings"):
            with gr.Row():
                with gr.Column(scale=1):

                    es_url = gr.Textbox(label="ES url connection",value="http://localhost:9200")
                    es_user = gr.Textbox(label="ES user",value="elastic")
                    es_pass = gr.Textbox(label="ES pass",value="changeme")

                with gr.Column(scale=1):
                    minio_url = gr.Textbox(label="Minio host",value="localhost:9000")
                    minio_access = gr.Textbox(label="Minio access key",value="AKIAIOSFODNN7EXAMPLE")
                    minio_secret = gr.Textbox(label="Minio secret key",value="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")

            with gr.Row():
                with gr.Column(scale=1):

                    gcp_svc_json = gr.Textbox(label="Google Application Credentials",value="service-account-vision.json")
                    gcp_location = gr.Textbox(label="Location",value="us-central-1")
                    project_id = gr.Textbox(label="Project Caption ID", value="Your project id")

                    endpoint_id = gr.Textbox(label="Endpoint Caption ID",value="Your endpoint id")
                    endpoint_vqa_id = gr.Textbox(label="Endpoint VQA ID",value="Your endpoint id")

                with gr.Column(scale=1):
                    model_name = gr.Dropdown(choices=["Salesforce/blip2-opt-2.7b"],label="Model Name",value="Salesforce/blip2-opt-2.7b")

                    num_captions = gr.Number(label="Total camptions",value=5)

                    qa_on = gr.Checkbox(label="Use QA?",value=True,interactive=True)
                    nucleus_sampling = gr.Checkbox(label="Nucleus Sampling?", value=True, interactive=True)

                    prompt_text = gr.Text(label="Prompt",value="Question: what object is in this image? Answer:")
                    prompt_long_text = gr.Text(label="Prompt", value="Question: what is the structure and geometry of this %s?")



            save_button = gr.Button("Save...")

            save_button.click(fn=save_settings, inputs=[es_url,es_user,es_pass,minio_url,minio_access,minio_secret,settings_state],
                                outputs=settings_state)

from fastapi import FastAPI, HTTPException
@app.get("/objects/{uid}", response_class=HTMLResponse)
def read_main(uid:int,request: Request):
    '''
    Get info about an object

    :return: HTML
    '''
    if "uid" in request.path_params:
        return templates.TemplateResponse(
            "object.html", {"request":request,"uid":request.query_params["uid"]})
    else:
        raise HTTPException(status_code=404, detail="Object ID not found")

# launch the flask application
app = gr.mount_gradio_app(app,demo,path="/search")
