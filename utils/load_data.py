import argparse
import objaverse
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
parser.add_argument('--max', metavar='-m', type=int, help='max test objects',default=100)

args = parser.parse_args()

if args.source == "objaverse":
    print("Loading ")

    uids = objaverse.load_uids()
    random_object_uids = random.sample(uids, args.max)
    annotations = objaverse.load_annotations()

    processes = multiprocessing.cpu_count()

    print("Using %d processes" % processes)

    local_files = objaverse.load_objects(
        uids=random_object_uids,
        download_processes=processes
    )

    INDEX_NAME = "objaverse"

    es = Elasticsearch([settings['es_url']], verify_certs=False,
                       basic_auth=(settings['es_user'], settings['es_pass']))

    es.indices.delete(index=INDEX_NAME, ignore=[400,404])

    mappings = {
        "properties": {
            "uid": {"type": "keyword"},
            "name": {"type": "text"},
            "description": {"type": "text"},
            'publishedAt': {
                "type": "date"
            }
        }
    }

    es.indices.create(index=INDEX_NAME,mappings=mappings)

    client = Minio(settings['minio_url'],
                   access_key=settings['minio_access'],
                   secret_key=settings['minio_secret'],
                   secure=False
                   )

    # Make the bucket if it doesn't exist.
    found = client.bucket_exists(INDEX_NAME)
    if not found:
        client.make_bucket(INDEX_NAME)
        print("Created bucket", INDEX_NAME)
    else:
        # TODO: delete the entire bucket also ...
        print("Bucket", INDEX_NAME, "already exists")

    local_files = objaverse.load_objects(
        uids=random_object_uids,
        download_processes=processes
    )

    for uid, path in local_files.items():
        print("UID: {0} File Path: {1}".format(uid, path))

        object_meta = annotations[uid]
        try:
            # add the annotation first
            res = es.index(index='objaverse', body=annotations[uid], refresh='true')
            print("document id: %s" % res.body['_id'])

            tags = Tags(for_object=True)
            subfields = ["uri", "uid","publishedAt"]

            for field in subfields:
                tags[field] = object_meta[field]

            ext = pathlib.Path(path).suffix

            # add into minio
            client.fput_object(
                INDEX_NAME, uid, path,metadata={"es_id" : res.body['_id'],"ext":ext},tags=tags
            )

            print(
                path, "successfully uploaded as object",
                uid, "to bucket", INDEX_NAME,
            )

        except elasticsearch.ElasticsearchWarning as wan:
            print(wan)

