"""Guardrails for importing generated project descriptions."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from import_generated_profiles import load_and_validate, validate_profile  # noqa: E402


def project(name='owner/ai-tool', identifier=42):
    return {
        'fullName': name, 'id': identifier, 'editorial': False,
        'description': 'An AI tool that searches documents and returns citations.',
        'readme': 'An AI tool that searches documents and returns citations.\n'
                  'Run locally with Python. It indexes files before answering questions.',
        'readmeSha': 'abc123', 'readmeUrl': f'https://github.com/{name}/blob/main/README.md',
        'url': f'https://github.com/{name}', 'sourceExcerpts': [],
    }


def ai_profile(name='owner/ai-tool'):
    return {
        'fullName': name, 'relevance': 'ai',
        'relevanceReason': '这是通过索引文档回答问题的 AI 工具。',
        'category': 'knowledge', 'related': [], 'kind': '应用 / 工具',
        'tags': ['文档问答'], 'ways': ['Python 库'],
        'summary': '索引本地文档并生成带有出处的问答结果。',
        'overview': ('该工具读取用户提供的文档，并先建立可搜索的索引。'
                     '提问时，它根据索引找到相关内容，再返回问题答案和对应出处。'
                     '资料显示它可以在本地通过 Python 运行，因此适合需要核对文档依据的问答场景。'
                     '目前资料只说明基础索引和查询流程，没有给出支持的文件格式、'
                     '模型提供方、准确率或硬件门槛；这些条件需要在实际部署前查看官方文档。'
                     '它的核心用途是把个人或团队的资料转为可查询内容，而不是通用数据库服务。'),
        'audience': '需要根据已有文档回答问题并核对出处的开发者。',
        'features': ['索引文档内容', '回答查询并给出出处'],
        'useCases': ['检索内部资料'], 'gettingStarted': [], 'requirements': [],
        'usage': '按照项目说明使用 Python 在本地运行。',
        'caveat': '资料未说明具体文件格式和硬件要求。',
        'evidence': [
            'An AI tool that searches documents and returns citations.',
            'Run locally with Python. It indexes files before answering questions.',
        ],
    }


def not_ai_profile(name='owner/plain-database'):
    result = ai_profile(name)
    result.update({
        'relevance': 'not-ai', 'relevanceReason': '该仓库是通用数据库，不提供专门 AI 功能。',
        'category': 'apps', 'kind': '应用 / 工具', 'tags': [], 'ways': [],
        'summary': '', 'overview': '', 'audience': '', 'features': [],
        'useCases': [], 'gettingStarted': [], 'requirements': [],
        'usage': '', 'caveat': '',
        'evidence': ['A general database for storing application records.'],
    })
    return result


class ImportGeneratedProfilesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.batch = Path(self.temp.name)
        self.ai = project()
        self.plain = project('owner/plain-database', 43)
        self.plain['description'] = 'A general database for storing application records.'
        self.plain['readme'] = self.plain['description']
        self.latest = {'projects': [self.ai, self.plain]}
        self.manifest = [
            {'fullName': p['fullName'], 'id': p['id'], 'readmeSha': p['readmeSha']}
            for p in self.latest['projects']
        ]
        self.profiles = [ai_profile(), not_ai_profile()]

    def validate(self, registry=None, require_complete=False):
        (self.batch / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        (self.batch / 'result-batch-0001.json').write_text(
            json.dumps({'profiles': self.profiles}, ensure_ascii=False), encoding='utf-8')
        return load_and_validate(self.batch, self.latest, registry or {},
                                 require_complete=require_complete)

    def test_imports_ai_and_only_lists_not_ai_as_candidate(self):
        accepted, candidates, missing = self.validate(require_complete=True)
        self.assertEqual(set(accepted), {'owner/ai-tool'})
        self.assertEqual(accepted['owner/ai-tool']['category'], 'knowledge')
        self.assertEqual(accepted['owner/ai-tool']['profileStatus'], 'generated')
        self.assertNotIn('reviewedAt', accepted['owner/ai-tool'])
        self.assertEqual(accepted['owner/ai-tool']['sourceUrls'], [self.ai['readmeUrl']])
        self.assertEqual(accepted['owner/ai-tool']['sourceReadmeSha'], 'abc123')
        self.assertEqual(accepted['owner/ai-tool']['generationModel'], 'gpt-6-astra')
        self.assertEqual(accepted['owner/ai-tool']['sourceEvidence'], self.profiles[0]['evidence'])
        self.assertEqual([x['fullName'] for x in candidates], ['owner/plain-database'])
        self.assertEqual(missing, [])

    def test_rejects_identity_and_source_drift(self):
        self.manifest[0]['id'] = 999
        with self.assertRaisesRegex(ValueError, 'name/ID mismatch'):
            self.validate()
        self.manifest[0]['id'] = 42
        self.manifest[0]['readmeSha'] = 'old'
        with self.assertRaisesRegex(ValueError, 'README changed'):
            self.validate()

    def test_rejects_ambiguous_repository_name(self):
        duplicate = copy.deepcopy(self.ai)
        duplicate['id'] = 44
        self.latest['projects'].append(duplicate)
        with self.assertRaisesRegex(ValueError, 'ambiguous repository identity'):
            self.validate()

    def test_rejects_existing_editorial_profile(self):
        with self.assertRaisesRegex(ValueError, 'refusing to overwrite'):
            self.validate(registry={'owner/ai-tool': {'summary': '已审核'}})

    def test_rejects_unsupported_evidence(self):
        self.profiles[0]['evidence'] = ['A fictional feature that was not written in the project README.']
        with self.assertRaisesRegex(ValueError, 'evidence is not'):
            self.validate()

    def test_rejects_placeholder_and_english_explanation(self):
        self.profiles[0]['summary'] = '该项目暂归入知识库方向，待中文核对。'
        with self.assertRaisesRegex(ValueError, 'placeholder'):
            self.validate()
        self.profiles[0]['summary'] = 'Searches documents.'
        with self.assertRaisesRegex(ValueError, 'Chinese explanation'):
            self.validate()

    def test_source_quote_can_contain_todos_word(self):
        quote = 'The agent preserves todos and handoffs across turns.'
        spanish_quote = 'Todo generado con texto a voz, sin grabar nada tú.'
        candidate = project()
        candidate['readme'] += '\n' + quote + '\n' + spanish_quote
        profile = ai_profile()
        profile['evidence'] = [quote, spanish_quote]
        validate_profile(profile, candidate)

    def test_rejects_wrong_enum_or_unknown_field(self):
        self.profiles[0]['kind'] = 'database'
        with self.assertRaisesRegex(ValueError, 'invalid kind'):
            self.validate()
        self.profiles[0]['kind'] = '应用 / 工具'
        self.profiles[0]['invented'] = True
        with self.assertRaisesRegex(ValueError, 'wrong fields'):
            self.validate()

    def test_rejects_repeated_template_and_duplicate_batch(self):
        duplicate = copy.deepcopy(self.ai)
        duplicate['fullName'] = 'owner/second-tool'
        duplicate['id'] = 45
        self.latest['projects'].append(duplicate)
        self.manifest.append({'fullName': duplicate['fullName'], 'id': duplicate['id'], 'readmeSha': 'abc123'})
        second = ai_profile(duplicate['fullName'])
        self.profiles.append(second)
        with self.assertRaisesRegex(ValueError, 'summary duplicates'):
            self.validate()
        self.profiles[-1]['summary'] = '另一个工具，索引本地文档并给出出处。'
        with self.assertRaisesRegex(ValueError, 'near-duplicate'):
            self.validate()
        self.profiles.pop()
        self.profiles.append(copy.deepcopy(self.profiles[0]))
        with self.assertRaisesRegex(ValueError, 'duplicate or unassigned'):
            self.validate()

    def test_requires_complete_only_when_requested(self):
        self.profiles.pop()
        self.assertEqual(self.validate()[2], ['owner/plain-database'])
        with self.assertRaisesRegex(ValueError, 'profiles missing'):
            self.validate(require_complete=True)


if __name__ == '__main__':
    unittest.main()
