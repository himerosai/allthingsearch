# in file task.py
from fastapi import FastAPI
from celery import shared_task, Celery
from datetime import datetime
import os
from dotenv import dotenv_values
import uvicorn
from minio import Minio
from minio.tagging import Tags

settings = dotenv_values("config.env")

app = FastAPI()

redis_url = os.getenv("REDIS_URL", settings['redis_url'])

celery = Celery(__name__, broker=redis_url,
                backend=redis_url,
                broker_connection_retry_on_startup=True)

def generate_render_minio(object_id:str):
    import subprocess
    import os, tempfile

    blender_path = settings['blender_path']
    render_path = settings['render_path']

    client = Minio(settings['minio_url'],
                access_key=settings['minio_key'],
                secret_key=settings['minio_secret'],
                secure=False
                )

    found = client.bucket_exists(settings['minio_bucket'])
    if found:
        # Get data of an object.
        try:
            obj_info = client.stat_object(settings['minio_bucket'], object_name=object_id)

            file_size = obj_info.size
            tags = obj_info.tags
            metadata = obj_info.metadata
            # now let's get the file size
            ext = metadata['X-Amz-Meta-Ext']

            print("Processing file size = {0} type = {1}".format(file_size, ext))

            tmp = tempfile.NamedTemporaryFile(delete=False,suffix=ext)

            obj_info = client.fget_object(settings['minio_bucket'], object_name= object_id,file_path=tmp.name)

            print("Processing with blender")
            result = subprocess.run(
                [blender_path, "-b", "-P", render_path, "--", "--object_path", tmp.name, "--parent_dir", "./renders"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                encoding='utf-8')

            out = result.stdout
            err = result.stderr

            lines = out.split("\n")
            header = lines[0]

            tags = Tags.new_object_tags()
            tags["status"] = "cap3d_views"
            tags["returnCode"] = str(result.returncode)

            client.set_object_tags(settings['minio_bucket'], object_id, tags)

            print(header)
            print("Result %d" % result.returncode)
            return result.returncode
        except Exception as e:
            print(e)
        finally:
            tmp.close()
            os.unlink(tmp.name)

            return 0
    else:
        return 1


def generate_render_path(obj_path:str):
    import subprocess

    blender_path = settings['blender_path']
    render_path = settings['render_path']

    # --object_path_pkl: point to a pickle file which store the object path
    # --parent_dir: the directory store the rendered images and their associated camera matrix
    # Rendered images & camera matrix will stored at partent_dir/Cap3D_imgs/

    # ./blender-3.4.1-linux-x64/blender -b -P render_script.py -- --object_path './example_material/example_object_path.pkl' --parent_dir './example_material'
    result = subprocess.run([blender_path, "-b","-P",render_path,"--", "--object_path", obj_path,"--parent_dir","./renders"],
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               stdin=subprocess.PIPE,
                               encoding='utf-8')

    out = result.stdout
    err = result.stderr

    lines = out.split("\n")
    header = lines[0]

    return result.returncode

@celery.task
def dummy_task(text:str):
    folder = "./files"
    os.makedirs(folder, exist_ok=True)
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%s")
    with open(f"{folder}/task-{now}.txt", "w") as f:
        f.write(text)


@app.get("/test/{text}")
async def run_test(text:str):
    dummy_task.delay(text)
    return {"message":text}


'''
celery -A fastapi_celery.celery worker --loglevel=info

Fastapi:
uvicorn main:app --reload

OR

fastapi run fastapi_celery.py
'''

#uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == '__main__':
    generate_render_minio("1f2b3e9f71c34c8965da4384aa0ddc96")
    #generate_render("./files/2968ed36911043359cc110067ab8b725.glb")