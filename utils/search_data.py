import argparse

from minio import Minio
import multiprocessing
import random
from elasticsearch import Elasticsearch
from minio.commonconfig import Tags
import elasticsearch
import pathlib

import urllib3
urllib3.disable_warnings()

random.seed(10)

from dotenv import dotenv_values

settings = dotenv_values("config.env")

parser = argparse.ArgumentParser(description='Load some test data')

parser.add_argument("--source",metavar="-s",type=str,default="objaverse")

parser.add_argument("--field",metavar="-f",type=str,default="description")
parser.add_argument("--value",metavar="-v",type=str,default="objaverse")
parser.add_argument('--max', metavar='-m', type=int, help='max test objects',default=10)

args = parser.parse_args()

if args.source == "objaverse":
    
    INDEX_NAME = "objaverse"

    es = Elasticsearch([settings['es_url']], verify_certs=False,
                       basic_auth=(settings['es_user'], settings['es_pass']))



    client = Minio(settings['minio_url'],
                   access_key=settings['minio_access'],
                   secret_key=settings['minio_secret'],
                   secure=False
                   )
    
    res = es.search(index=INDEX_NAME, body={"query": {"match_all": {}},"size":args.max})

    for doc in res['hits']['hits']:
        print(f"{doc['_id']}, {doc['_source'].keys()}")
        if doc['_source']['description']:
            print(doc['_source']['description'])
