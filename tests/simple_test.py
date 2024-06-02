import unittest

settings = {"es_url":"http://localhost:9200","es_user":"elastic","es_pass":"changeme"
}
class IndexObjectsCase(unittest.TestCase):
    def test_1(self):
        '''
        Is it installed

        :return:
        '''

        import objaverse
        print(objaverse.__version__)

    def test_2(self):
        '''
        Check the database is full and type is correct

        :return:
        '''

        import objaverse
        uids = objaverse.load_uids()

        self.assertEqual(len(uids),798759,msg="All objects are ready")

        self.assertEqual(type(uids), type([]), msg="Uids are correct")

    def test_3(self,max_obj = 10):
        '''
        Load the first 100 objects into our databse

        :return:
        '''
        import objaverse
        from dotmap import DotMap
        from elasticsearch import Elasticsearch
        import elasticsearch

        es = Elasticsearch([settings['es_url']], verify_certs=False,
                           basic_auth=(settings['es_user'], settings['es_pass']))

        es.indices.delete(index='objaverse', ignore_unavailable=True)

        es.indices.create(index='objaverse')

        uids = objaverse.load_uids()
        uids = uids[:max_obj]
        annotations = objaverse.load_annotations(uids)

        subfields = ["uri","uid","name","description","publishedAt","user.uid","user.username"]
        for uid in uids:
            annotation = DotMap(annotations[uid])

            try:
                res = es.index(index='objaverse', body=annotations[uid])

                self.assertEqual(res.meta.status,201)

                self.assertEqual(res.body['result'],"created")

                print("document id: %s" % res.body['_id'])
            except elasticsearch.ElasticsearchWarning as wan:
                print(wan)

        es.indices.delete(index='objaverse', ignore_unavailable=True)

if __name__ == '__main__':
    unittest.main()
