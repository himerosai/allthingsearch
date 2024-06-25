import unittest

from dotenv import dotenv_values

settings = dotenv_values("config.env")

BASE_PATH = "/media"
class IndexObjectsCase(unittest.TestCase):
    def test_1(self):
        '''
        Is it installed

        :return:
        '''

        import objaverse
        print(objaverse.__version__)
        print("Base PATH %s " % objaverse.BASE_PATH)

        # change it ....

    def test_2(self):
        '''
        Check the database is full and type is correct

        :return:
        '''

        import objaverse
        uids = objaverse.load_uids()

        self.assertEqual(len(uids),798759,msg="All objects are ready")

        self.assertEqual(type(uids), type([]), msg="Uids are correct")

    def test_4(self,max_obj = 10):
        '''
        Load the first 100 objects into our databse

        :return:
        '''
        import objaverse
        from elasticsearch import Elasticsearch
        import elasticsearch

        print("Base PATH %s " % objaverse.BASE_PATH)

        objaverse.BASE_PATH = "/media/data/.objaverse"

        INDEX_NAME = "test_index_2"
        # TODO: need to use the generated certificate during setup
        es = Elasticsearch([settings['es_url']], verify_certs=False,
                           basic_auth=(settings['es_user'], settings['es_pass']))

        es.indices.delete(index=INDEX_NAME, ignore_unavailable=True)

        es.indices.create(index=INDEX_NAME)

        uids = objaverse.load_uids()
        uids = uids[:max_obj]
        annotations = objaverse.load_annotations(uids)

        subfields = ["uri","uid","name","description","publishedAt","user.uid","user.username"]
        for uid in uids:

            try:
                res = es.index(index='objaverse', body=annotations[uid], refresh = 'true' )

                self.assertEqual(res.meta.status,201)

                self.assertEqual(res.body['result'],"created")

                print("document id: %s" % res.body['_id'])
            except elasticsearch.ElasticsearchWarning as wan:
                print(wan)

        # count objects
        res = es.count(index=INDEX_NAME)["count"]
        
        self.assertEqual(res,max_obj)
        es.indices.delete(index=INDEX_NAME, ignore_unavailable=True)

    def test_3(self,max_obj = 10):
        '''
        Load the first 100 objects into our databse

        :return:
        '''
        import objaverse
        from minio import Minio
        import multiprocessing

        objaverse.BASE_PATH = "/media/data/.objaverse"

        processes = multiprocessing.cpu_count()

        INDEX_NAME = "testindex3"

        uids = objaverse.load_uids()

        local_files = objaverse.load_objects(
            uids=uids[:100],
            download_processes=processes
        )

        client = Minio(settings['minio_url'],
            access_key=settings['minio_access'],
            secret_key=settings['minio_secret'],
            secure = False
        )

        # Make the bucket if it doesn't exist.
        found = client.bucket_exists(INDEX_NAME)
        if not found:
            client.make_bucket(INDEX_NAME)
            print("Created bucket", INDEX_NAME)
        else:
            print("Bucket", INDEX_NAME, "already exists")

        for uid,path in local_files.items():
            print("UID: {0} File Path: {1}".format(uid,path))
            # Upload the file, renaming it in the process
            client.fput_object(
                INDEX_NAME, uid, path,
            )
            print(
                path, "successfully uploaded as object",
                uid, "to bucket", INDEX_NAME,
            )

if __name__ == '__main__':
    unittest.main()
