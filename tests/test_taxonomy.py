import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from collect import classify
from taxonomy import normalize_ways

class TaxonomyTests(unittest.TestCase):
    def test_aliases_share_filters_without_losing_distinct_interfaces(self):
        self.assertEqual(normalize_ways(['命令行','CLI','Web界面','Web UI','REST API','Python SDK','Python库','MCP 服务']),
                         ['CLI','Web UI','REST API','Python SDK','Python 库','MCP'])
        self.assertEqual(normalize_ways(['Docker','Docker Compose','Kubernetes','浏览器扩展']),
                         ['Docker','Docker Compose','Kubernetes','浏览器扩展'])

    def test_collection_preserves_reviewed_purpose_and_specific_tags(self):
        profile={'category':'audio','related':[],'kind':'框架 / SDK',
                 'tags':['语音识别','浏览器'],'ways':['命令行','CLI','Python库']}
        result=classify({'full_name':'org/speech','name':'speech','topics':['agent','llm'],
                         'description':'speech recognition library'},'supports speech',{'org/speech':profile})
        self.assertEqual(result['category'],'audio')
        self.assertEqual(result['related'],[])
        self.assertEqual(result['tags'],profile['tags'])
        self.assertEqual(result['ways'],['CLI','Python 库'])
        self.assertEqual(profile['ways'],['命令行','CLI','Python库'])
