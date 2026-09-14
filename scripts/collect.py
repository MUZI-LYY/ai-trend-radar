#!/usr/bin/env python3
"""GitHub-only collector. Uses Actions GITHUB_TOKEN or gh's normal API client.
Never reads credentials from gh, never fabricates missing history or overwrites dated archives.
"""
import argparse, concurrent.futures, datetime as dt, hashlib, json, os, re, subprocess, sys, time, urllib.request, urllib.error
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from ranking import period_starts, chart_entries
UTC = dt.timezone.utc
CATEGORIES = {
 'agents': ('AI Agent', '自主任务执行、工具调用与多智能体协作', ['agent','multi-agent','autogpt','crewai']),
 'coding': ('AI 编程', '代码生成、审查与开发辅助', ['coding','code-assistant','code-review','copilot','aider','opencode','claude-code']),
 'models': ('模型与推理', '模型运行、推理加速与本地部署', ['inference','llm-inference','llama','ollama','vllm','transformers','quantization']),
 'knowledge': ('RAG 与知识库', '知识检索、文档处理与问答', ['rag','knowledge-base','document-parsing','docling','ragflow','llama-index']),
 'automation': ('工作流与自动化', '可视化工作流和业务系统集成', ['workflow','automation','n8n','dify','flowise']),
 'visual': ('图像与视频', '图像生成、编辑与多模态理解', ['image-generation','text-to-image','diffusion','comfyui','video-generation']),
 'audio': ('语音与音频', '语音识别、合成与音频处理', ['text-to-speech','speech','audio','whisper','tts','voice','music']),
 'apps': ('AI 应用与交互', '对话、搜索、写作与 AI 客户端', ['chatbot','chat','webui','perplexica','assistant','search-engine']),
 'devtools': ('训练与开发工具', '训练、评测、数据处理与可观测性', ['fine-tuning','training','evaluation','mlops','machine-learning','deep-learning']),
 'learning': ('学习与资源', '教程、课程和学习资料', ['awesome','tutorial','course','for-beginners','from-scratch','guide','resources']),
}
SEEDS = ['ollama/ollama','langgenius/dify','langchain-ai/langchain','langchain-ai/langgraph','open-webui/open-webui','n8n-io/n8n','huggingface/transformers','vllm-project/vllm','ggml-org/llama.cpp','Comfy-Org/ComfyUI','AUTOMATIC1111/stable-diffusion-webui','openai/whisper','QwenAudio/CosyVoice','Blaizzy/mlx-audio','infiniflow/ragflow','docling-project/docling','microsoft/markitdown','run-llama/llama_index','crewAIInc/crewAI','microsoft/autogen','Significant-Gravitas/AutoGPT','Aider-AI/aider','OpenHands/OpenHands','anthropics/claude-code','google-gemini/gemini-cli','anomalyco/opencode','FlowiseAI/Flowise','Mintplex-Labs/anything-llm','ItzCrazyKns/Vane','lobehub/lobehub','unslothai/unsloth','hiyouga/LlamaFactory','langfuse/langfuse','rasbt/LLMs-from-scratch','microsoft/generative-ai-for-beginners','f/prompts.chat','github/spec-kit','modelcontextprotocol/servers','browser-use/browser-use','firecrawl/firecrawl']

def atomic_json(path, value):
 path.parent.mkdir(parents=True, exist_ok=True)
 tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n');tmp.replace(path)

def api(endpoint):
 token=os.environ.get('GITHUB_TOKEN')
 for attempt in range(3):
  try:
   if token:
    req=urllib.request.Request('https://api.github.com/'+endpoint,headers={'Authorization':'Bearer '+token,'User-Agent':'ai-trend-radar','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2026-03-10'})
    with urllib.request.urlopen(req, timeout=30) as response:return json.load(response)
   result=subprocess.run(['gh','api','-X','GET','-H','X-GitHub-Api-Version: 2026-03-10',endpoint],capture_output=True,text=True,timeout=40)
   if result.returncode:raise RuntimeError(result.stderr.strip()[:180])
   return json.loads(result.stdout)
  except (urllib.error.HTTPError,urllib.error.URLError,RuntimeError,subprocess.TimeoutExpired,json.JSONDecodeError) as e:
   if attempt==2 or ('404' in str(e)):raise RuntimeError(f'{endpoint.split("?")[0]}: {e}') from None
   time.sleep(2**attempt*3)

def flatten_history(weeks, end_date):
 """Use the API week bucket's UTC date label, never pretend these are Beijing midnights."""
 daily={}
 for week in weeks:
  if not isinstance(week,dict) or not isinstance(week.get('week'),(int,float)):raise ValueError('Invalid week')
  days=week.get('days')
  if not isinstance(days,list) or len(days)!=7 or any(type(x) is not int or x<0 for x in days):raise ValueError('Invalid day values')
  if week.get('total')!=sum(days):raise ValueError('Weekly total mismatch')
  base=dt.datetime.fromtimestamp(week['week'],UTC).date()
  for i,value in enumerate(days):
   date=(base+dt.timedelta(days=i)).isoformat()
   if date<=end_date:
    if date in daily and daily[date]!=value:raise ValueError('Conflicting history buckets')
    daily[date]=value
 return daily

def period_total(daily,start,end,created):
 start=max(start,created[:10])
 if start>end:return 0
 date=dt.date.fromisoformat(start);last=dt.date.fromisoformat(end);total=0
 while date<=last:
  key=date.isoformat()
  if key not in daily:return None
  total+=daily[key];date+=dt.timedelta(days=1)
 return total

def strip_readme(md):
 md=re.sub(r'```.*?```','',md,flags=re.S)
 md=re.sub(r'<!--.*?-->','',md,flags=re.S)
 md=re.sub(r'!\[[^\]]*\]\([^)]*\)','',md)
 md=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',md)
 md=re.sub(r'<[^>]*>','',md)
 md=re.sub(r'\[\]\([^)]*\)', '', md)
 lines=[re.sub(r'^[#*>\-\s]+','',s).strip() for s in md.splitlines()]
 return '\n\n'.join(s for s in lines if len(s)>35 and not s.startswith(('http','|')) and not any(x in s.lower() for x in ['badge','sponsor','discord.gg']))[:8000]

def classify(repo, readme, editorial):
 full=repo['full_name'];info=editorial.get(full.lower(),{})
 topics=repo.get('topics',[])
 text=' '.join([full,repo.get('description') or '',*topics]).lower()
 scores={k:sum(2 if t in topics else 1 for t in ts if t in text) for k,(_,_,ts) in CATEGORIES.items()}
 primary=info.get('category') or max(scores,key=scores.get)
 if not any(scores.values()) and not info:primary='apps'
 if primary not in CATEGORIES:raise ValueError(f'Unknown editorial category for {full}: {primary}')
 secondary=info.get('related')
 if secondary is None:secondary=[k for k in sorted(scores,key=scores.get,reverse=True) if scores[k] and k!=primary][:2]
 if not isinstance(secondary,list) or any(k not in CATEGORIES for k in secondary):raise ValueError(f'Invalid editorial related categories for {full}')
 secondary=list(dict.fromkeys(k for k in secondary if k!=primary))
 kind=info.get('kind') or ('学习资源' if primary=='learning' else '模型与引擎' if primary=='models' else '框架 / SDK' if re.search(r'framework|library|sdk',text) else '应用 / 工具')
 tags=info.get('tags') or [t for t in topics if t not in ('ai','artificial-intelligence','python','typescript','llm')][:4] or ['能力待核实']
 ways=info.get('ways',[])
 source_url=f'https://github.com/{full}'
 summary=info.get('summary') or f'{repo["name"]} 属于{CATEGORIES[primary][0]}方向。仓库简介：{repo.get("description") or "作者暂未提供简介。"}'
 overview=info.get('overview') or f'{repo["name"]} 是一个主要使用 {repo.get("language") or "仓库所列技术"} 的{kind}，归入{CATEGORIES[primary][0]}方向。分类依据来自仓库简介和 Topics，具体功能请结合下方 README 原文确认。'
 usage=info.get('usage') or f'建议先阅读仓库 README 中的 Quick Start、Installation 或 Usage 部分，确认当前版本的依赖和运行方式。该仓库提供了 GitHub 源码入口'+('和项目主页。' if repo.get('homepage') else '。')
 caveat=info.get('caveat') or '安装步骤、外部服务费用和硬件要求以项目当前文档为准；仓库公开不代表所有模型、第三方服务或商业使用都没有限制。'
 return {'category':primary,'related':secondary,'kind':kind,'tags':tags,'ways':ways,'summary':summary,'overview':overview,'audience':info.get('audience') or f'希望了解或评估{CATEGORIES[primary][0]}能力的开发者与产品研究者。','features':info.get('features',[]),'useCases':info.get('useCases',[]),'gettingStarted':info.get('gettingStarted',[]),'requirements':info.get('requirements',[]),'usage':usage,'caveat':caveat,'editorial':bool(info),'readme':strip_readme(readme),'readmeUrl':source_url+'/blob/'+repo.get('default_branch','main')+'/README.md','reviewedAt':info.get('reviewedAt'), 'classificationBasis':'编辑整理，依据仓库简介与 README' if info else '依据仓库简介与 Topics 自动归类，待复核'}

def trending():
 # HTML is used only for candidate discovery. Reported Trending counts never enter the rankings.
 with urllib.request.urlopen(urllib.request.Request('https://github.com/trending',headers={'User-Agent':'ai-trend-radar'}),timeout=25) as r:html=r.read().decode()
 names=[]
 for article in re.findall(r'<article\b.*?</article>',html,re.S):
  h=re.search(r'<h2\b.*?</h2>',article,re.S)
  m=re.search(r'href="/([\w.-]+/[\w.-]+)"',h.group(0) if h else '')
  if m:names.append(m.group(1))
 return names

def collect_one(full, previous, editorial, end, year_start):
 repo=api('repos/'+full)
 if repo.get('private') or repo.get('fork') or repo.get('disabled'):return None
 fetched=dt.datetime.now(UTC).isoformat()
 # GitHub Contents API provides README content + SHA without embedding any HTML in the website.
 readme='';readme_url=None;sha=None;warnings=[]
 try:
  r=api('repos/'+repo['full_name']+'/readme');sha=r.get('sha');readme_url=r.get('html_url')
  import base64
  readme=base64.b64decode(r.get('content','')).decode('utf-8',errors='replace')[:100000]
 except Exception as e:warnings.append('README 获取失败')
 history=[];history_status='ok'
 try:
  # Two pages normally cover a full calendar year. Stop early at creation or the required boundary.
  for page in range(1,4):
   weeks=api(f'repos/{repo["full_name"]}/stargazers/history?per_page=30&page={page}')
   if not isinstance(weeks,list):raise ValueError('Unexpected star history response')
   if not weeks and page==1:raise ValueError('Empty history is unavailable, not all zero')
   history+=weeks
   if len(weeks)<30 or (weeks and dt.datetime.fromtimestamp(weeks[-1]['week'],UTC).date().isoformat()<=year_start):break
  daily=flatten_history(history,end)
 except Exception as e:daily={};history_status='unavailable';warnings.append('Star 历史暂不可用')
 profile=classify(repo,readme,editorial)
 if readme_url:profile['readmeUrl']=readme_url
 first=previous.get('firstSeen') if previous else fetched[:10]
 created=repo['created_at']
 metrics={p:period_total(daily,s,end,created) if history_status=='ok' else None for p,s in period_starts(end).items()}
 prev_stars=previous.get('stars') if previous else None
 return {**profile,'id':repo['id'],'fullName':repo['full_name'],'name':repo['name'],'owner':repo['owner']['login'],'avatar':repo['owner']['avatar_url'],'url':repo['html_url'],'homepage':repo.get('homepage') if str(repo.get('homepage','')).startswith(('https://','http://')) else None,'stars':repo['stargazers_count'],'forks':repo['forks_count'],'language':repo.get('language') or '未标注','license':(repo.get('license') or {}).get('spdx_id') or '未明确','topics':repo.get('topics',[]),'description':repo.get('description') or '', 'archived':repo['archived'],'createdAt':created,'pushedAt':repo['pushed_at'],'fetchedAt':fetched,'firstSeen':first,'readmeSha':sha,'metrics':metrics,'historyStatus':history_status,'history':[{'date':d,'stars':v} for d,v in sorted(daily.items())],'warnings':warnings,'netSincePrevious':repo['stargazers_count']-prev_stars if prev_stars is not None else None,'netBaselineAt':previous.get('fetchedAt') if previous else None}

def select_candidates(previous, candidates, limit, new_limit):
 """Never drop tracked records when the budget is lowered; bound only new work."""
 new=[name for key,name in candidates.items() if key not in previous]
 room=max(0,limit-len(previous))
 return [r['fullName'] for r in previous.values()]+new[:min(max(0,new_limit),room)]

def retain_previous(projects, previous, end):
 """Prefer fresh records on redirects and preserve missing projects without old ranks."""
 by_id={}
 for project in projects:
  old=by_id.get(project['id'])
  if old is None or project['fetchedAt']>old['fetchedAt']:by_id[project['id']]=project
 for old in previous.values():
  if old['id'] not in by_id:
   by_id[old['id']]={**old,'stale':True,'metrics':{p:None for p in period_starts(end)},'warnings':sorted(set(old.get('warnings',[])+['本次未获取到更新，保留上次记录']))}
  else:
   # A new candidate name can redirect to an already tracked repository ID.
   # Keep its observation baseline even if that candidate won the fresh deduplication.
   fresh=by_id[old['id']]
   if old.get('firstSeen'):fresh['firstSeen']=old['firstSeen']
   if 'stars' in old and 'stars' in fresh:
    fresh['netSincePrevious']=fresh['stars']-old['stars']
    fresh['netBaselineAt']=old['fetchedAt']
 return list(by_id.values())

def missing_period_history(projects):
 if not any(not p.get('stale') and any(v is not None for v in p['metrics'].values()) for p in projects):
  raise ValueError('No usable fresh period metrics: previous published data preserved')
 return [p['fullName'] for p in projects if not p.get('stale') and any(v is None for v in p['metrics'].values())]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=180);parser.add_argument('--new-limit',type=int,default=8);parser.add_argument('--no-discover',action='store_true');parser.add_argument('--refresh',action='store_true');args=parser.parse_args()
 now=dt.datetime.now(UTC);capture_date=now.astimezone(dt.timezone(dt.timedelta(hours=8))).date().isoformat();end=(now.date()-dt.timedelta(days=1)).isoformat();year_start=min(period_starts(end).values())
 latest_path=ROOT/'public/data/latest.json';latest=json.loads(latest_path.read_text()) if latest_path.exists() else {'projects':[]}
 snapshot_path=ROOT/'public/data/snapshots'/f'{capture_date}.json'
 if snapshot_path.exists() and not args.refresh:print('Already collected '+capture_date+'; archived snapshot preserved.');return
 editorial=json.loads((ROOT/'data/editorial.json').read_text()) if (ROOT/'data/editorial.json').exists() else {}
 excluded_path=ROOT/'data/excluded.json'
 excluded={name.lower() for name in json.loads(excluded_path.read_text())} if excluded_path.exists() else set()
 previous={r['fullName'].lower():r for r in latest['projects'] if r['fullName'].lower() not in excluded}
 candidates={key:r['fullName'] for key,r in previous.items()}
 for n in SEEDS:candidates[n.lower()]=n
 warnings=[];queries=['topic:llm stars:>300 archived:false','topic:ai-agents stars:>100 archived:false','topic:generative-ai stars:>300 archived:false','topic:machine-learning stars:>1000 archived:false']
 if not args.no_discover:
  from urllib.parse import urlencode
  for query in queries:
   try:
    data=api('search/repositories?'+urlencode({'q':query,'sort':'updated','per_page':10}))
    if data.get('incomplete_results'):warnings.append('部分搜索结果不完整')
    for r in data.get('items',[]):
     if not r.get('fork'):candidates[r['full_name'].lower()]=r['full_name']
   except Exception as e:warnings.append('项目搜索部分不可用');print(str(e),file=sys.stderr)
  try:
   for name in trending():
    # Trending is not AI-only: metadata check below filters candidates conservatively.
    candidates.setdefault(name.lower(),name)
  except Exception:warnings.append('Trending 发现暂不可用')
 # Update every tracked repository, and reserve a bounded budget for new candidates.
 candidates={key:value for key,value in candidates.items() if key not in excluded}
 new=[name for key,name in candidates.items() if key not in previous]
 room=max(0,args.limit-len(previous))
 names=select_candidates(previous,candidates,args.limit,args.new_limit)
 if new and not room:warnings.append('达到收录预算上限，已有项目继续更新，新项目发现暂停；可调整采集 limit。')
 projects=[];failures=[]
 def work(name):
  result=collect_one(name,previous.get(name.lower()),editorial,end,year_start)
  if result and name.lower() not in previous and name.lower() not in {s.lower() for s in SEEDS}:
   text=' '.join([result['fullName'],result['description'],*result['topics']]).lower()
   if not re.search(r'\b(ai|llm|rag|agent|agents|gpt|ml|mcp)\b|artificial.intelligence|machine.learning|deep.learning|diffusion|neural|语音|智能|模型',text):return None
  return result
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
  futures={executor.submit(work,name):name for name in names}
  for f in concurrent.futures.as_completed(futures):
   name=futures[f]
   try:
    result=f.result()
    if result:projects.append(result);print(f'Collected {result["fullName"]}: {result["stars"]} stars; history={result["historyStatus"]}',flush=True)
   except Exception as e:failures.append(name);print(f'Failed {name}: {e}',file=sys.stderr,flush=True)
 if not projects:raise SystemExit('No fresh projects: previous published data preserved')
 # Do not publish a misleading severely incomplete batch.
 if len(failures)>max(3,len(names)*0.2):raise SystemExit('Too many failed repositories: previous published data preserved')
 projects=retain_previous(projects,previous,end)
 projects.sort(key=lambda p:(-p['stars'],p['fullName'].lower()))
 missing_history=missing_period_history(projects)
 if missing_history:warnings.append(f'{len(missing_history)} 个项目的部分 Star 历史不可用，缺失指标不参与对应榜单。')
 payload={'schemaVersion':2,'date':capture_date,'capturedAt':now.isoformat(),'completedAt':dt.datetime.now(UTC).isoformat(),'periodEnd':end,'periodStarts':period_starts(end),'source':'GitHub REST API','metric':'官方 Star 历史日统计','timezoneNote':'日期按官方 week 时间戳的 UTC 日期展开；源统计日边界不保证与 UTC 或北京时间午夜一致。日榜取已结束的来源统计日。','scope':'本站收录的 AI 相关公开仓库，并非 GitHub 全量项目。','categories':[{'id':k,'label':v[0],'description':v[1]} for k,v in CATEGORIES.items()],'status':'partial' if failures or missing_history or any(p.get('stale') for p in projects) else 'complete','warnings':sorted(set(warnings)),'failedRepositories':failures,'missingHistoryRepositories':missing_history,'projects':projects}
 # First successfully published daily archive is immutable; refresh only changes latest.json.
 if not snapshot_path.exists():atomic_json(snapshot_path,payload)
 atomic_json(latest_path,payload)
 index=[{'date':p.stem,'file':'snapshots/'+p.name} for p in sorted(snapshot_path.parent.glob('*.json'),reverse=True)]
 atomic_json(ROOT/'public/data/index.json',{'snapshots':index})
 entries=chart_entries(json.loads(p.read_text()) for p in snapshot_path.parent.glob('*.json'))
 atomic_json(ROOT/'public/data/board-history.json',{'chartSize':30,'entries':entries})
 from backfill_history import update_history
 update_history(projects,end)
 # Do not retain per-person stars. Only repo metadata and aggregate day counts are stored.
 print(json.dumps({'projects':len(projects),'historyAvailable':sum(p['historyStatus']=='ok' and not p.get('stale') for p in projects),'date':capture_date,'status':payload['status']}),flush=True)
if __name__=='__main__':main()
