"""Stable filter vocabulary: merge spelling variants without inventing capabilities."""
KINDS = frozenset(['应用 / 工具', '框架 / SDK', '模型与引擎', '开发工具', '技能 / 插件',
                   'MCP 服务', '学习资源', '研究实现', '数据集', '协议 / 标准'])
WAY_GROUPS = {
    'CLI': ['命令行', '终端', '终端界面', 'CLI Agent'],
    'Web UI': ['Web', '网页界面', 'Web应用', 'Web界面', '网页应用', 'Web平台', '浏览器', 'Web查看器', 'Web预览'],
    '桌面应用': ['桌面', '桌面安装', '桌面界面', '桌面客户端', '桌面查看器', '本地应用'],
    '自托管': ['自部署', '源码部署', '自部署Web'],
    '本地部署': ['本地运行', '本地服务', '本地网页', '本地Web', '本地Web应用'],
    '文档阅读': ['阅读资料', '在线阅读', '文档学习', '在线资料', '文章阅读', '网页阅读', '文档', '报告阅读', '画廊阅读', 'Markdown'],
    '示例代码': ['代码示例', '示例项目', '交互示例'],
    'Notebook': ['笔记本'],
    'Python SDK': ['PythonSDK'],
    'Python 库': ['Python库'],
    'Agent 技能': ['Agent技能', '技能安装', '技能集成', 'Claude Code技能'],
    '插件': ['Agent 插件', 'Agent插件', '插件安装', '桌面插件', '桌面扩展'],
    '编辑器插件': ['IDE插件', '编辑器扩展'],
    'MCP': ['MCP 服务'],
    'REST API': ['RESTAPI'],
    'HTTP API': ['HTTP服务'],
    '云服务': ['云部署', '在线服务'],
    '在线演示': ['官方在线体验', 'Web演示'],
    '移动应用': ['移动端'],
    'VS Code': ['VSCode'],
    'Claude Code': ['ClaudeCode'],
}
WAY_ALIASES = {alias: canonical for canonical, aliases in WAY_GROUPS.items() for alias in aliases}


def normalize_ways(values):
    return list(dict.fromkeys(WAY_ALIASES.get(value.strip(), value.strip()) for value in values if value.strip()))
