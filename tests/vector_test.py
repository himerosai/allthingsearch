import unittest

from dotenv import dotenv_values

settings = dotenv_values("config.env")


class VectorCase(unittest.TestCase):
    def test_1(self):
        '''
        Is it installed

        :return:
        '''
        from langchain_elasticsearch import ElasticsearchStore
        from langchain_openai import OpenAIEmbeddings
        import langchain_openai

    def test_2(self):
        '''
        Is it installed

        :return:
        '''
        import elasticsearch
        from langchain_elasticsearch import ElasticsearchStore
        from langchain_openai import OpenAIEmbeddings

        es_client= elasticsearch.Elasticsearch(
            hosts=[settings['es_url']],
            basic_auth=(settings['es_user'],settings['es_pass']),
            max_retries=10,
        )

        embedding = OpenAIEmbeddings()
        elastic_vector_search = ElasticsearchStore(
            index_name="test_index",
            es_connection=es_client,
            embedding=embedding,
        )

if __name__ == '__main__':
    unittest.main()
