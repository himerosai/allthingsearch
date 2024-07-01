# in file task.py
from fastapi import FastAPI
from celery import shared_task, Celery
from datetime import datetime
import os
from dotenv import dotenv_values
import uvicorn

settings = dotenv_values("config.env")

app = FastAPI()

redis_url = os.getenv("REDIS_URL", settings['redis_url'])

celery = Celery(__name__, broker=redis_url,
                backend=redis_url,
                broker_connection_retry_on_startup=True)

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
