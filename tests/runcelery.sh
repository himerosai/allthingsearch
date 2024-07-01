#!/bin/bash

# run the fastapi
uvicorn backend:app --reload --host 0.0.0.0 --port 8000

# run the worker
celery -A backend.celery worker --loglevel=info
# run the UI
celery -A main.app flower --address='0.0.0.0' --port='5555' --basic-auth=allthings:allthings