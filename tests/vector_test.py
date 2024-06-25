import unittest

from dotenv import dotenv_values

settings = dotenv_values("config.env")




class VectprCase(unittest.TestCase):
    def test_1(self):
        '''
        Is it installed

        :return:
        '''
        from langchain_elasticsearch import ElasticsearchStore
        from langchain_openai import OpenAIEmbeddings
        from langchain_openai import OpenAIEmbeddings
        print(langchain_openai.__version__)

if __name__ == '__main__':
    unittest.main()
