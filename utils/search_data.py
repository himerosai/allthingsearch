import argparse

from minio import Minio
import multiprocessing
import random
from elasticsearch import Elasticsearch
from minio.commonconfig import Tags
import elasticsearch
import pathlib
from esutils import *
from minioutils import *
import sys
import urllib3
urllib3.disable_warnings()

random.seed(10)

from dotenv import dotenv_values

settings = dotenv_values("config.env")

parser = argparse.ArgumentParser(description='Load some test data')

parser.add_argument("--source",metavar="-s",type=str,default="objaverse")
parser.add_argument("--operation",metavar="-o",type=str,default="fields")
parser.add_argument("--field",metavar="-f",type=str,default="description")
parser.add_argument("--value",metavar="-v",type=str,default="objaverse")
parser.add_argument('--max', metavar='-m', type=int, help='max test objects',default=1)

args = parser.parse_args()

if args.source == "objaverse":
    es = Elasticsearch([settings['es_url']], verify_certs=False,
                        basic_auth=(settings['es_user'], settings['es_pass']), request_timeout=30)

    

    INDEX_NAME = "objaverse"

    if args.operation == "search":


        minio_client = Minio(settings['minio_url'],
                    access_key=settings['minio_access'],
                    secret_key=settings['minio_secret'],
                    secure=False
                    )
        
        calculate_bucket_size(minio_client,settings['minio_bucket'])

        print("Beginning match all....")
        es.indices.refresh(index=INDEX_NAME)

        res = es.search(index=INDEX_NAME, body={"query": {"match_all": {}},"size":args.max})

        for doc in res['hits']['hits']:
            print(f"{doc['_id']}, {doc['_source'].keys()}")
            if doc['_source']['description']:
                print(doc['_source']['description'])
                print(doc['_source']['name'])
                print(doc['_source']['publishedAt'])
                print(doc['_source']['uid'])

        print("Match all done")
        
        res2 = es.search(index=INDEX_NAME, body={"query": {"query_string": {"query":"description:piece AND name:Chess"}},"size":args.max})

        for doc in res2['hits']['hits']:
            print(f"{doc['_id']}, {doc['_source'].keys()}")
            if doc['_source']['description']:
                print(doc['_source']['description'])
                print(doc['_source']['publishedAt'])
                print(doc['_source']['uid'])

    if args.operation == "fields":
        fields = get_index_fields(es,INDEX_NAME)
        print(fields)