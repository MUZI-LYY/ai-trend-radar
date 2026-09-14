"""Batch repository metadata through GraphQL; no extraction of stored credentials."""
import json
import os
import subprocess
import urllib.request


FIELDS = '''databaseId name nameWithOwner description url homepageUrl stargazerCount
forkCount isArchived isFork isPrivate isDisabled createdAt pushedAt
owner { login avatarUrl } primaryLanguage { name } licenseInfo { spdxId }
defaultBranchRef { name } repositoryTopics(first:100) { nodes { topic { name } } }'''


def graphql(query):
    token = os.environ.get('GITHUB_TOKEN')
    if token:
        request = urllib.request.Request('https://api.github.com/graphql',
            data=json.dumps({'query': query}).encode(),
            headers={'Authorization': 'Bearer '+token, 'User-Agent': 'ai-trend-radar',
                     'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    result = subprocess.run(['gh', 'api', 'graphql', '-f', 'query='+query],
                            capture_output=True, text=True, timeout=60)
    # GraphQL can return useful partial data alongside an error for a deleted repo.
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise RuntimeError('GitHub GraphQL metadata request failed') from None
    if result.returncode and not payload.get('data'):
        raise RuntimeError('GitHub GraphQL metadata request failed')
    return payload


def rest_metadata(node):
    """Map to the REST-shaped contract consumed by collect_one and classify."""
    if not node or node.get('databaseId') is None:
        return None
    return {'id': node['databaseId'], 'full_name': node['nameWithOwner'],
            'name': node['name'], 'description': node.get('description'),
            'html_url': node['url'], 'homepage': node.get('homepageUrl'),
            'stargazers_count': node['stargazerCount'], 'forks_count': node['forkCount'],
            'archived': node['isArchived'], 'fork': node['isFork'],
            'private': node['isPrivate'], 'disabled': node.get('isDisabled', False),
            'created_at': node['createdAt'], 'pushed_at': node.get('pushedAt'),
            'owner': {'login': node['owner']['login'], 'avatar_url': node['owner']['avatarUrl']},
            'language': (node.get('primaryLanguage') or {}).get('name'),
            'license': {'spdx_id': (node.get('licenseInfo') or {}).get('spdxId')},
            'default_branch': (node.get('defaultBranchRef') or {}).get('name') or 'main',
            'topics': [item['topic']['name'] for item in (node.get('repositoryTopics') or {}).get('nodes', [])]}


def batch_metadata(names, batch_size=25, request=None):
    """Return metadata keyed by requested lower-case name; missing entries need fallback.

    A bad batch does not discard other batches. REST fallback is controlled by the
    collector's shared request budget, never performed invisibly by this helper.
    """
    request = request or graphql
    if not 1 <= batch_size <= 30:
        raise ValueError('Metadata batch size must be between 1 and 30')
    names = list(dict.fromkeys(names))
    result = {}
    for offset in range(0, len(names), batch_size):
        batch = names[offset:offset+batch_size]
        fields = []
        for i, full in enumerate(batch):
            owner, name = full.split('/', 1)
            fields.append(f'r{i}:repository(owner:{json.dumps(owner)},name:{json.dumps(name)})'+'{'+FIELDS+'}')
        try:
            payload = request('query {'+' '.join(fields)+'}')
            data = payload.get('data') or {}
            for i, full in enumerate(batch):
                mapped = rest_metadata(data.get('r'+str(i)))
                if mapped:
                    result[full.lower()] = mapped
        except (RuntimeError, OSError, ValueError, subprocess.TimeoutExpired):
            continue
    return result
