"""Evidence-first fallback profiles for repositories without an editorial profile.

English source material belongs in sourceExcerpts/README, never in Chinese
explanatory fields. No translation calls or inferred capabilities are made.

Usage: profile.update(build_source_profile(repo, readme, readme_url=readme_url))
Call only when no manual editorial record exists. Does not set category, tags,
editorial, review dates, or ranking metadata.
"""
from __future__ import annotations

import html
import re
from typing import Any

_PATTERNS = {
    'features': r'features?|capabilities|what.{0,15}(?:does|offers|can)|why\s|功能|特性|能力|亮点',
    'start': r'quick\s*start|getting\s*started|installation|installing|^install$|setup|basic\s*usage|^usage$|快速开始|快速上手|安装|使用方法|开始使用',
    'requirements': r'prerequisites?|requirements?|system\s*requirements|supported\s*(?:platform|hardware)|依赖|要求|运行环境|硬件|前置条件',
    'limits': r'limitations?|caveats?|known\s*issues|compatibility|licens|限制|注意事项|许可|已知问题|兼容',
    'cases': r'use\s*cases|examples?|applications|适用场景|应用场景|示例',
}
_NOISE = re.compile(r'badge|shields\.io|sponsor|donat|discord\.gg|buy me a coffee|star history|star us|follow us|join (?:our|the) community|联系我们|赞助|交流群', re.I)
_REQUIREMENT = re.compile(r'\b(?:requires?|prerequisites?|minimum|recommended|only supports?|supported (?:on|platforms))\b|(?:需要|要求|至少|仅支持|推荐).{0,50}(?:版本|显存|内存|Python|Node|GPU|Docker|环境|系统)', re.I)
_CAPABILITY = re.compile(r'\b(?:supports?|provides?|includes?|lets you|allows you|features?|can (?:run|build|create|generate|use|manage))\b|支持|提供|可以|能够|功能', re.I)
_LIMIT = re.compile(r'\b(?:not supported|not (?:yet |currently )?(?:available|implemented|production)|experimental|deprecated|maintenance mode|non-commercial|limitations?)\b|不支持|实验性|非商业|维护模式|已弃用|已知问题', re.I)


def _plain(value: str, limit: int = 650) -> str:
    value = re.sub(r'!\[[^\]]*\]\([^\n]*?\)', '', value)
    value = re.sub(r'!\[[^\]]*\]\[[^\]]*\]', '', value)
    value = re.sub(r'\[([^\]]+)\]\([^\n]*?\)', r'\1', value)
    value = re.sub(r'\[([^\]]+)\]\[[^\]]*\]', r'\1', value)
    value = re.sub(r'<[^>]*>', '', value)
    value = html.unescape(value)
    value = re.sub(r'^[\s#>*\-\d.)]+', '', value)
    value = re.sub(r'\*\*|__|~~|`', '', value)
    value = re.sub(r'(?<!\w)[*_]([^*_\n]+)[*_](?!\w)', r'\1', value)
    value = re.sub(r'\s+', ' ', value).strip()
    if len(value) > limit:
        value = value[:limit].rsplit(' ', 1)[0] + '…' if ' ' in value[:limit] else value[:limit] + '…'
    return value


def _sections(md: str) -> list[dict[str, str]]:
    md = re.sub(r'<!--.*?-->', '', md[:100000], flags=re.S)
    # Script/style bodies must not turn into visible explanatory text.
    md = re.sub(r'<(?:script|style)\b[^>]*>.*?</(?:script|style)>', '', md, flags=re.I | re.S)
    heading = 'README'
    sections: list[dict[str, str]] = []
    paragraph: list[str] = []
    code: list[str] = []
    fenced = False

    def flush() -> None:
        if paragraph:
            text = _plain(' '.join(paragraph))
            if len(text) >= 28 and text.count(' | ') < 4 and len(re.findall(r'[\U0001F1E6-\U0001F1FF]{2}', text)) < 4 and not _NOISE.search(text) and not re.match(r'^(https?://|\[|\|)', text):
                sections.append({'heading': heading, 'text': text, 'kind': 'text'})
            paragraph.clear()

    for line in md.splitlines():
        if re.match(r'^\s*(`{3,}|~{3,})', line):
            flush()
            if fenced:
                # Commands are quoted as source, never run or represented as reviewed advice.
                text = '\n'.join(code).strip()
                if text and len(text) <= 1200:
                    sections.append({'heading': heading, 'text': text, 'kind': 'code'})
                code = []
            fenced = not fenced
            continue
        if fenced:
            code.append(line)
            continue
        match = re.match(r'^\s{0,3}#{1,6}\s+(.+)', line)
        if match:
            flush()
            heading = _plain(match.group(1), 120)
            continue
        if not line.strip():
            flush()
            continue
        if re.match(r'^\s*(?:[-*+]\s|\d+[.)]\s)', line):
            flush()
            paragraph.append(line)
            flush()
            continue
        if re.match(r'^\s*\[[^\]]+\]:', line) or re.match(r'^\s*[-=]{3,}\s*$', line):
            continue
        paragraph.append(line)
    flush()
    return sections


def _unique(items: list[dict[str, str]], limit: int) -> list[dict[str, str]]:
    seen: set[str] = set()
    result = []
    for item in items:
        key = item['text'].casefold()
        if key not in seen:
            result.append(item)
            seen.add(key)
        if len(result) >= limit:
            break
    return result


def build_source_profile(repo: dict[str, Any], readme: str, *, readme_url: str | None = None) -> dict[str, Any]:
    """Return attributed source content in the site's existing profile fields.

    ``repo`` accepts GitHub REST/search names or a stored Project object. Missing
    README data is explicit; Topics remain discovery labels, not capabilities.
    """
    full = repo.get('full_name') or repo.get('fullName') or repo.get('name') or '项目'
    description = _plain(repo.get('description') or '', 650)
    source = readme_url or repo.get('readmeUrl') or f'https://github.com/{full}'
    blocks = _sections(readme or '')
    text_blocks = [b for b in blocks if b['kind'] == 'text' and not re.search(r'contribut|sponsor|translat|community|citation|acknowledg|赞助|贡献者|致谢', b['heading'], re.I)]

    def select(section: str, fallback: re.Pattern[str] | None = None, maximum: int = 4) -> list[dict[str, str]]:
        selected = [b for b in text_blocks if re.search(_PATTERNS[section], b['heading'], re.I)]
        if not selected and fallback:
            selected = [b for b in text_blocks if fallback.search(b['text'])]
        return _unique(selected, maximum)

    features = select('features', _CAPABILITY)
    start = select('start', maximum=3)
    if not start:
        start = _unique([b for b in blocks if b['kind'] == 'code' and re.search(_PATTERNS['start'], b['heading'], re.I)], 3)
    requirements = select('requirements', _REQUIREMENT, maximum=4)
    limitations = select('limits', _LIMIT, maximum=3)
    cases = select('cases', maximum=3)
    # Introduction must not be taken from install, licensing or contributor sections.
    intros = [b for b in text_blocks if not any(re.search(_PATTERNS[k], b['heading'], re.I) for k in ('start', 'requirements', 'limits'))]
    intro = next((b for b in intros if b['text'] != description and len(b['text']) >= 70), None)
    if not features:
        features = _unique([b for b in intros if _CAPABILITY.search(b['text'])], 3)
    if not features and description:
        features = [{'heading': 'GitHub description', 'text': description, 'kind': 'text'}]

    category = repo.get('category') or ''
    category_label = {
        'agents': 'AI Agent', 'coding': 'AI 编程', 'models': '模型与推理',
        'knowledge': 'RAG 与知识库', 'automation': '工作流与自动化',
        'visual': '图像与视频', 'audio': '语音与音频',
        'apps': 'AI 应用与交互', 'devtools': '训练与开发工具',
        'learning': '学习与资源',
    }.get(category, 'AI 开源项目')
    summary = f'该项目暂归入{category_label}方向，具体用途待中文核对。'
    overview = (f'该仓库是本站收录的{category_label}方向项目。当前分类依据仓库简介与标签，'
                '尚未完成逐项中文解读；其功能、适用场景和使用条件不能仅凭分类确认。'
                + ('下方保留作者的原始文档摘录，可核对项目定位及具体能力。' if readme else
                   '本次未取得项目文档，请到仓库核对项目定位及具体能力。'))
    usage = ('已从项目文档提取上手资料，可在下方原文区域核对具体步骤和版本要求。'
             if start else '当前资料未提取到明确的安装或使用步骤，请查看项目的官方文档。')
    caveat = ('原文中有关于限制或兼容性的说明，请阅读官方文档确认适用条件。' if limitations else
              '当前摘录未确认项目特有的兼容性和许可限制，使用前请核对官方文档与许可证。')
    caveat += ' 本页为自动来源整理，作者的性能或能力宣称未经本站独立验证。'
    selected = _unique(([intro] if intro else []) + features + start + requirements + limitations + cases, 20)
    return {
        'summary': summary,
        'overview': overview,
        'features': [],
        'usage': usage,
        'audience': '可按下方作者提供的功能、场景和运行条件判断是否适合自己的任务；当前资料未对目标用户进行人工确认。',
        'useCases': [],
        'requirements': [],
        'gettingStarted': ['打开官方文档，按当前版本的说明确认安装和使用步骤。'] if start else [],
        'caveat': caveat,
        'profileSource': 'readme-extract' if blocks else 'repository-description',
        'sourceExcerpts': [{'section': b['heading'], 'text': b['text'], 'url': source} for b in selected],
    }
