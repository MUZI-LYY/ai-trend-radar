import { useEffect, useMemo, useState } from 'react';
import { ArrowDown, ArrowLeft, ArrowUpRight, CalendarDays, Check, CircleHelp, Clock3, Database, ExternalLink, Flame, GitBranch as Github, Layers3, Radio, Radar, Search, ShieldCheck, Sparkles, Star, TrendingUp, Trophy, X } from 'lucide-react';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { Dataset, Project } from './types';

import PeriodSelector from './PeriodSelector';
import {withLatestProfiles} from './editorial';
import CustomTimeRange, {type TimeRange} from './CustomTimeRange';
import {boardStateKey,parseBoardState,boardQueryKey,pageWindow,type BoardPeriod,type PageSize} from './board-state';
import Pagination from './Pagination';
import {useBoardNavigation} from './useBoardNavigation';
import {aggregateDailyBoards,type DailyBoard,type WeeklyBoard} from './weekly';
import {replayHistory,prepareDailyRange,type HistoryIndex,type HistoryData} from './history';
import {parseHistoryResponse} from './history-source';
import {archiveReady,normalizeDataset,cumulativeTenure,compareNames,type BoardHistory,type CumulativeChart} from './ranking';
import {completeLatest} from './latest-data';
import Spotlights from './Spotlights';

const repoUrl = 'https://github.com/MUZI-LYY/ai-trend-radar';
const periods: {id:BoardPeriod;label:string;en:string;icon:typeof Flame}[]=[{id:'daily',label:'日榜',en:'DAILY',icon:Flame},{id:'weekly',label:'周榜',en:'WEEKLY',icon:CalendarDays},{id:'monthly',label:'月榜',en:'MONTHLY',icon:CalendarDays},{id:'yearly',label:'年榜',en:'YEARLY',icon:TrendingUp},{id:'all',label:'历史总榜',en:'ALL TIME',icon:Trophy},{id:'custom',label:'自定义时间',en:'CUSTOM',icon:CalendarDays}];
const format=(n:number)=>new Intl.NumberFormat('en-US').format(n);
const short=(n:number)=>n>=1e6?(n/1e6).toFixed(1)+'m':n>=1e3?(n/1e3).toFixed(1)+'k':String(n);
const when=(s:string)=>new Date(s).toLocaleString('zh-CN',{timeZone:'Asia/Shanghai',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
const color:Record<string,string>={development:'#597bb7',web:'#48a891',data:'#9b71be',infrastructure:'#d18e53',other:'#93a3ae',agents:'#6878dc',coding:'#e8a355',models:'#4680b8',knowledge:'#419d87',automation:'#aa75bb',visual:'#df7e95',audio:'#d1a23e',apps:'#47a0b1',devtools:'#869458',learning:'#8391a4'};
const score=(p:Project,period:BoardPeriod)=>period==='custom'?(p.customGrowth??null):period==='all'?p.stars:p.metrics[period];
function rank(items:Project[],period:BoardPeriod,retrospective=false){return items.filter(p=>!p.stale&&score(p,period)!==null).sort((a,b)=>(score(b,period)??0)-(score(a,period)??0)||(retrospective?0:b.stars-a.stars)||compareNames(a.fullName,b.fullName));}
function Picker({value,onChange,items,label}:{value:string;onChange:(v:string)=>void;items:{value:string;label:string}[];label:string}){return <Select value={value} onValueChange={v=>v!==null&&onChange(String(v))}><SelectTrigger aria-label={label} className="picker"><SelectValue>{items.find(i=>i.value===value)?.label??value}</SelectValue></SelectTrigger><SelectContent>{items.map(i=><SelectItem key={i.value} value={i.value}>{i.label}</SelectItem>)}</SelectContent></Select>}
function MiniChart({history}:{history:Project['history']}){const points=history.slice(-14);if(points.length<2)return <span className="muted">积累中</span>;const max=Math.max(...points.map(p=>p.stars),1);const line=points.map((p,i)=>`${i*92/(points.length-1)},${26-p.stars/max*23}`).join(' ');return <svg className="sparkline" viewBox="0 0 94 29" role="img" aria-label="最近14个来源统计日的每日新增 Star"><polyline points={line} fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/><circle cx="92" cy={26-points.at(-1)!.stars/max*23} r="2.4" fill="currentColor"/></svg>}
function HistoryChart({project}:{project:Project}){const [span,setSpan]=useState(30);const points=project.history.slice(-span);if(points.length<2)return <div className="empty">有效历史不足，暂无曲线。缺失值不会被视为零。</div>;const max=Math.max(...points.map(p=>p.stars),1);const w=720,h=180;const line=points.map((p,i)=>`${i*w/(points.length-1)},${h-8-p.stars/max*(h-20)}`).join(' ');return <section className="chart-section"><div className="section-head"><div><h2>Star 增长轨迹</h2><p>每日官方历史统计 · 非累计曲线</p></div><div className="segmented">{[30,90,365].map(n=><button aria-pressed={span===n} onClick={()=>setSpan(n)} key={n}>{n} 天</button>)}</div></div><div className="chart-wrapper"><span className="chart-max">{format(max)}</span><svg viewBox={`-5 -5 ${w+10} ${h+15}`} role="img" aria-label={`${points[0].date} 至 ${points.at(-1)!.date} 的每日 Star 统计`}><defs><linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1"><stop stopColor="#269c70" stopOpacity=".2"/><stop offset="1" stopColor="#269c70" stopOpacity="0"/></linearGradient></defs>{[0,1,2,3].map(i=><line key={i} x1="0" y1={i*h/3} x2={w} y2={i*h/3} stroke="#e5ece8" strokeDasharray="4 4"/>)}<polygon points={`0,${h} ${line} ${w},${h}`} fill="url(#chartFill)"/><polyline points={line} fill="none" stroke="#23825e" strokeWidth="2.5" strokeLinejoin="round"/></svg><div className="chart-dates"><span>{points[0].date}</span><span>{points.at(-1)!.date}</span></div></div><details className="source-details"><summary>查看曲线的原始数值</summary><div className="history-values">{points.slice().reverse().map(p=><div key={p.date}><span>{p.date}</span><strong>+{format(p.stars)}</strong></div>)}</div></details></section>}

export default function App(){
 const [route,setRoute]=useState(window.location.hash);
 useEffect(()=>{const update=()=>setRoute(window.location.hash);window.addEventListener('hashchange',update);return()=>window.removeEventListener('hashchange',update)},[]);
 const mode=route.startsWith('#/github')?'github':'ai';
 return <BoardApp key={mode} mode={mode}/>;
}

function BoardApp({mode}:{mode:'ai'|'github'}){
 const isGithub=mode==='github';
 const boardHref=isGithub?'#/github':'#/';
 const aboutHref=isGithub?'#/github/about':'#/about';
 const projectHref=isGithub?'#/github/project/':'#/project/';
 const dataRoot=isGithub?'data/github/':'data/';
 const historyFile='history.json.gz';
 const stateKey=isGithub?'github-radar:board:v1':boardStateKey;
 const [savedState]=useState(()=>{try{const stored=sessionStorage.getItem(stateKey);const parsed=parseBoardState(stored);return isGithub&&!stored?{...parsed,period:'all' as BoardPeriod}:parsed}catch{return parseBoardState(null)}});
 const [dataCache]=useState(()=>new Map<string,Promise<unknown>>());
 const [dataVersion,setDataVersion]=useState(()=>Date.now().toString());
 const [standardData,setData]=useState<Dataset|null>(null),[error,setError]=useState(''),[standardLoading,setLoading]=useState(false);
 const [bootstrapData,setBootstrapData]=useState<Dataset|null>(null);
 const [historyIndex,setHistoryIndex]=useState<HistoryIndex|null>(null),[dailyScope,setDailyScope]=useState<'top'|'all'>(savedState.dailyScope);
 const [boardHistory,setBoardHistory]=useState<BoardHistory|null>(null);
 const [cumulativeChart,setCumulativeChart]=useState<CumulativeChart|null>(null);
 const [weeklyResult,setWeeklyResult]=useState<{key:string;board:WeeklyBoard}|null>(null);
 const [weeklyLoading,setWeeklyLoading]=useState(false);
 const [weeklyError,setWeeklyError]=useState(''),[boardHistoryError,setBoardHistoryError]=useState('');
 const [hash,setHash]=useState(window.location.hash),[period,setPeriod]=useState<BoardPeriod>(savedState.period),[category,setCategory]=useState(savedState.category),[search,setSearch]=useState(savedState.search),[language,setLanguage]=useState(savedState.language),[kind,setKind]=useState(savedState.kind),[tag,setTag]=useState(savedState.tag),[way,setWay]=useState(savedState.way),[maintenance,setMaintenance]=useState(savedState.maintenance),[date,setDate]=useState(savedState.date);
 const full=hash.startsWith(projectHref)?decodeURIComponent(hash.slice(projectHref.length)):null;
 const filtersNeedFull=!!search||language!=='all'||kind!=='all'||!!tag||way!=='all'||maintenance!=='all';
 const needsFull=hash==='#/spotlights'||date!=='latest'||period!=='daily'||dailyScope!=='top'||category!=='all'||filtersNeedFull||!!(full&&bootstrapData&&!bootstrapData.projects.some(p=>p.fullName.toLowerCase()===full.toLowerCase()));
 const [periodDates,setPeriodDates]=useState<Partial<Record<BoardPeriod,string>>>(savedState.periodDates);
 const [pageSize,setPageSize]=useState<PageSize>(savedState.pageSize),[advancedOpen,setAdvancedOpen]=useState(savedState.advancedOpen);
 const [pagination,setPagination]=useState({key:boardQueryKey(savedState),page:savedState.page});
 const aggregated=period==='weekly'||period==='monthly'||period==='custom';
 const aggregatePeriod=period==='custom'?'custom':period==='monthly'?'monthly':'weekly';
 const aggregateLabel=period==='custom'?'区间榜':period==='monthly'?'月榜':'周榜';
 const [customRange,setCustomRange]=useState<TimeRange|null>(savedState.customRange);
 const [customResult,setCustomResult]=useState<({range:TimeRange}&ReturnType<typeof prepareDailyRange>)|null>(null);
 const [customLoading,setCustomLoading]=useState(false),[customError,setCustomError]=useState('');
 const customReady=!!customRange&&customResult?.range.start===customRange.start&&customResult?.range.end===customRange.end;
 const data=period==='custom'&&customReady?customResult!.data:needsFull&&!standardData?.listComplete?null:standardData;
 const loading=standardLoading||(period==='custom'&&customLoading)||!!(needsFull&&!standardData?.listComplete);
 useEffect(()=>{
  if(period!=='custom'||!customRange)return;
  let ignore=false;setCustomLoading(true);setCustomError('');
  const get=<T,>(file:string):Promise<T>=>{if(!dataCache.has(file))dataCache.set(file,fetch(import.meta.env.BASE_URL+`${dataRoot}${file}`,{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('区间数据暂时无法加载，请重试。');return file.endsWith('.json.gz')?parseHistoryResponse<T>(r):r.json()}).catch(e=>{dataCache.delete(file);throw e}));return dataCache.get(file)! as Promise<T>};
  Promise.all([get<Dataset>('latest-bootstrap.json').then(bootstrap=>completeLatest(bootstrap,get,dataCache)),get<HistoryData>(historyFile)]).then(([latest,history])=>{
   const result=prepareDailyRange(normalizeDataset(latest),history,customRange.start,customRange.end);
   if(!ignore)setCustomResult({range:customRange,...result});
  }).catch(e=>{if(!ignore)setCustomError(String(e.message))}).finally(()=>{if(!ignore)setCustomLoading(false)});
  return()=>{ignore=true};
 },[period,customRange,dataCache,dataVersion,dataRoot,historyFile]);

 useEffect(()=>{
  let ignore=false;setLoading(true);setError('');
  const get=<T,>(file:string):Promise<T>=>{if(!dataCache.has(file))dataCache.set(file,fetch(import.meta.env.BASE_URL+`${dataRoot}${file}`,{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('榜单暂时无法加载，请稍后重试。');return file.endsWith('.json.gz')?parseHistoryResponse<T>(r):r.json()}).catch(e=>{dataCache.delete(file);throw e}));return dataCache.get(file)! as Promise<T>};
  const load=async()=>{
   const bootstrap=await get<Dataset>('latest-bootstrap.json');
   const latest=needsFull?await completeLatest(bootstrap,get,dataCache):bootstrap;
   if(date.startsWith('history:')){const history=await get<HistoryData>(historyFile);return {bootstrap,data:replayHistory(normalizeDataset(latest),history,date.slice(8))}}
   if(date==='latest')return {bootstrap,data:normalizeDataset(latest)};
   const snapshot=await get<Dataset>(`snapshots/${date}.json`);
   return {bootstrap,data:{...withLatestProfiles(normalizeDataset(snapshot),latest),listComplete:true}};
  };
  load().then(({bootstrap,data})=>{if(!ignore){setBootstrapData(bootstrap);setData(data)}}).catch(e=>{if(!ignore)setError(String(e.message))}).finally(()=>{if(!ignore)setLoading(false)});return()=>{ignore=true};
 },[date,needsFull,dataVersion,dataCache,dataRoot,historyFile]);
 // A long-lived tab should notice a newer published collection without requiring a reload.
 const latestCompletedAt=bootstrapData?.completedAt;
 useEffect(()=>{
  if(date!=='latest'||!latestCompletedAt)return;
  let cancelled=false,checking=false,lastCheck=0;
  const check=async()=>{
   if(document.visibilityState!=='visible'||checking||Date.now()-lastCheck<60_000)return;
   checking=true;lastCheck=Date.now();
   try{
    const response=await fetch(import.meta.env.BASE_URL+dataRoot+'latest-bootstrap.json',{cache:'no-cache'});
    if(!response.ok)return;
    const current=await response.json() as Dataset;
    if(!cancelled&&current.completedAt!==latestCompletedAt){dataCache.clear();setDataVersion(Date.now().toString())}
   }catch{/* Keep the last verified board until the next check. */}
   finally{checking=false}
  };
  const onVisible=()=>{void check()};
  const timer=window.setInterval(onVisible,15*60_000);
  window.addEventListener('focus',onVisible);document.addEventListener('visibilitychange',onVisible);
  return()=>{cancelled=true;window.clearInterval(timer);window.removeEventListener('focus',onVisible);document.removeEventListener('visibilitychange',onVisible)};
 },[date,latestCompletedAt,dataCache,dataRoot]);
 useEffect(()=>{fetch(import.meta.env.BASE_URL+dataRoot+'history-index.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(setHistoryIndex).catch(()=>{});},[dataVersion,dataRoot]);

 useEffect(()=>{fetch(import.meta.env.BASE_URL+dataRoot+'board-history.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(value=>{setBoardHistory(value);setBoardHistoryError('')}).catch(()=>setBoardHistoryError('日榜索引加载失败，暂时无法可靠汇总日榜。'));},[dataVersion,dataRoot]);
 useEffect(()=>{fetch(import.meta.env.BASE_URL+dataRoot+'cumulative-chart.json',{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error();return r.json()}).then(setCumulativeChart).catch(()=>setCumulativeChart(null));},[dataVersion,dataRoot]);
 const retrospective=data?.viewType==='retrospective';
 const retrospectiveCoverage=retrospective&&data?{eligible:data.projects.length,complete:data.projects.filter(p=>period==='custom'?p.customGrowth!==null:p.metrics[period==='all'?'daily':period]!==null).length}:null;
 const boardTime=(p:Project)=>{const t=cumulativeTenure(p.id,data!.periodEnd,cumulativeChart);return !t?'累计在榜待核实':t.days?`累计在榜 ${t.days} 天 · 首次 ${t.since}`:'有效记录内未进入日榜 TOP 30';};
 const weeklyKey=data?`${period}:${date}:${data.completedAt}:${data.periodEnd}:${period==='custom'?customRange?.start:''}`:'';
 const weeklyBoard=weeklyResult?.key===weeklyKey?weeklyResult.board:null;
 const awaitingBoard=aggregated&&(period!=='custom'||!!customRange)&&(!weeklyBoard||weeklyLoading);
 useEffect(()=>{
  if(!aggregated||!data||loading||!boardHistory||(period==='custom'&&!customReady))return;
  let ignore=false;setWeeklyLoading(true);setWeeklyError('');setWeeklyResult(null);
  const target=period==='custom'?customResult!.boardData:data;const start=period==='custom'?customRange!.start:target.periodStarts[aggregatePeriod as 'weekly'|'monthly'];
  const anchor=period==='custom'?customResult!.anchor:retrospective?'retrospective':date==='latest'?'latest':'snapshot';
  const records=boardHistory.entries.filter(e=>e.date>=start&&e.date<target.periodEnd&&archiveReady(e));
  if(!records.length){
   setWeeklyResult({key:weeklyKey,board:aggregateDailyBoards(target,[],anchor,[],aggregatePeriod,customRange?.start)});
   setWeeklyLoading(false);
   return()=>{ignore=true};
  }
  const file='snapshot-boards.json';
  if(!dataCache.has(file))dataCache.set(file,fetch(import.meta.env.BASE_URL+`${dataRoot}${file}`,{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('日榜快照读取失败');return r.json()}).catch(error=>{dataCache.delete(file);throw error}));
  void (dataCache.get(file) as Promise<{completedAt:string;snapshots:Dataset[]}>).then(async bundle=>{
   const latest=await dataCache.get('latest-full') as Dataset;
   if(ignore)return;
   if(bundle.completedAt!==latest.completedAt)throw Error('榜单正在更新，请重新加载。');
   const byCapture=new Map(bundle.snapshots.map(snapshot=>[snapshot.date,snapshot]));
   const results=records.map(record=>({data:byCapture.get(record.capturedDate)??null,date:record.date}));
   const snapshots=results.flatMap(r=>r.data?[withLatestProfiles(r.data,latest)]:[]);
   setWeeklyResult({key:weeklyKey,board:aggregateDailyBoards(target,snapshots,anchor,anchor==='snapshot'?results.filter(r=>!r.data).map(r=>r.date):[],aggregatePeriod,customRange?.start)});
  }).catch(error=>{if(!ignore)setWeeklyError(String(error))}).finally(()=>{if(!ignore)setWeeklyLoading(false)});
  return()=>{ignore=true};
 },[period,data,date,loading,boardHistory,dataCache,dataVersion,dataRoot,weeklyKey,retrospective,aggregated,aggregatePeriod,customReady,customResult,customRange]);
 const listedProject=data?.projects.find(p=>p.fullName.toLowerCase()===full?.toLowerCase())??weeklyBoard?.rows.find(r=>r.project.fullName.toLowerCase()===full?.toLowerCase())?.project;
 const [detailData,setDetailData]=useState<{id:number;completedAt:string;readme:string;history:Project['history']}|null>(null);
 const [detailError,setDetailError]=useState('');
 useEffect(()=>{
  if(!listedProject||listedProject.readme!==undefined)return;
  let ignore=false;setDetailError('');
  const file=`project-details/${listedProject.id%(bootstrapData?.detailShardCount??data?.detailShardCount??64)}.json`;
  if(!dataCache.has(file))dataCache.set(file,fetch(import.meta.env.BASE_URL+`${dataRoot}${file}`,{cache:'no-cache'}).then(r=>{if(!r.ok)throw Error('项目详情读取失败');return r.json()}).catch(error=>{dataCache.delete(file);throw error}));
  (dataCache.get(file) as Promise<{id:number;readme:string;history:Project['history']}[]>).then(rows=>{
   const row=rows.find(item=>item.id===listedProject.id);
   if(!row)throw Error('项目详情未找到');
   if(!ignore)setDetailData({...row,completedAt:data!.completedAt});
  }).catch(error=>{if(!ignore)setDetailError(String(error))});
  return()=>{ignore=true};
 },[listedProject,date,data?.completedAt,data?.detailShardCount,bootstrapData?.detailShardCount,dataCache,dataVersion,dataRoot]);
 const detail=detailData&&detailData.id===listedProject?.id&&detailData.completedAt===data?.completedAt?detailData:null;
 const project=useMemo(()=>listedProject&&detail?{...listedProject,readme:detail.readme,history:retrospective?listedProject.history:detail.history}:listedProject,[listedProject,detail,retrospective]);
 const methodology=hash===aboutHref;
 const showingSpotlights=hash==='#/spotlights';
 useEffect(()=>{document.title=showingSpotlights?'有趣项目 · AI Radar':project?`${project.name} · ${isGithub?'GitHub 总榜':'AI Radar'}`:isGithub?'GitHub 总榜 · 开源趋势观察':'AI Radar · 开源趋势观察';},[project,isGithub,showingSpotlights]);
 const allRanked=useMemo(()=>period==='custom'&&!customReady?[]:aggregated?(weeklyBoard?.rows??[]).map(r=>({...r.project,stale:false,...(period==='custom'?{customGrowth:r.growth}:{metrics:{...r.project.metrics,[aggregatePeriod]:r.growth}})})):rank(data?.projects??[],period,retrospective),[data,period,retrospective,weeklyBoard,customReady,aggregated,aggregatePeriod]);
 const weeklyById=useMemo(()=>new Map(weeklyBoard?.rows.map(r=>[r.project.id,r])??[]),[weeklyBoard]);
 const rankedScope=useMemo(()=>period==='daily'&&dailyScope==='top'?allRanked.filter(p=>(p.metrics.daily??0)>0).slice(0,30):allRanked,[allRanked,period,dailyScope]);
 const categoryRanked=useMemo(()=>rankedScope.filter(p=>category==='all'||p.category===category||p.related.includes(category)),[rankedScope,category]);
 const filtered=useMemo(()=>categoryRanked.filter(p=>(!search||[p.fullName,p.summary,...p.tags,...p.topics].join(' ').toLowerCase().includes(search.toLowerCase()))&&(language==='all'||p.language===language)&&(kind==='all'||p.kind===kind)&&(!tag||p.tags.includes(tag))&&(way==='all'||p.ways.includes(way))&&(maintenance==='all'||(maintenance==='archived'?p.archived:!p.archived))),[categoryRanked,search,language,kind,tag,way,maintenance]);
 const boardState=useMemo(()=>({period,category,search,language,kind,tag,way,maintenance,date,dailyScope,periodDates,customRange,advancedOpen,pageSize}),[period,category,search,language,kind,tag,way,maintenance,date,dailyScope,periodDates,customRange,advancedOpen,pageSize]);
 const queryKey=boardQueryKey(boardState);
 const requestedPage=pagination.key===queryKey?pagination.page:1;
 const paging=pageWindow(filtered.length,requestedPage,pageSize);
 const boardReady=!!data&&!loading&&!awaitingBoard;
 const {scrollToResults,resetPosition}=useBoardNavigation(hash,setHash,boardReady,`${queryKey}:${paging.page}:${advancedOpen}`,boardHref);
 useEffect(()=>{try{sessionStorage.setItem(stateKey,JSON.stringify({...boardState,page:boardReady?paging.page:requestedPage}))}catch{/* Browsing still works without session storage. */}},[boardState,boardReady,paging.page,requestedPage,stateKey]);
 function changePage(page:number){scrollToResults();setPagination({key:queryKey,page})}
 function changePageSize(size:PageSize){scrollToResults();setPageSize(size);setPagination({key:'',page:1})}
 const languages=[...new Set(data?.projects.map(p=>p.language)??[])].sort();const kinds=[...new Set(data?.projects.map(p=>p.kind)??[])].sort();const ways=[...new Set(data?.projects.flatMap(p=>p.ways)??[])].sort();
 const selectedPeriod=periods.find(p=>p.id===period)!;
 const leaders=allRanked.slice(0,20);const counts=(data?.categories??[]).map(c=>({...c,count:leaders.filter(p=>p.category===c.id).length})).filter(c=>c.count).sort((a,b)=>b.count-a.count);
 const noGithubGrowth=isGithub&&period!=='all'&&(data?.bootstrapStats?.rankedDaily??0)===0;
 const archivedView=date!=='latest';const outdated=data&&Date.now()-new Date(data.completedAt).getTime()>36*3600*1000;
 function clear(){setSearch('');setLanguage('all');setKind('all');setTag('');setWay('all');setMaintenance('all');}
 const filterActive=filtersNeedFull;
 const categoryLabel=(id:string)=>data?.categories.find(c=>c.id===id)?.label??id;
 function selectTag(t:string){setDailyScope('all');setTag(t);window.location.hash=boardHref;}
 function home(){resetPosition();setPagination({key:'',page:1});dataCache.clear();setData(null);setBootstrapData(null);setDataVersion(Date.now().toString());setPeriod('daily');setDate('latest');setDailyScope('top');setCategory('all');clear()}
 function changePeriod(p:BoardPeriod){setPeriod(p);if(p!=='custom')setDate(periodDates[p]??'latest')}
 function choosePeriodEnd(end:string){const next=end===(bootstrapData?.periodEnd??historyIndex?.end)?'latest':'history:'+end;setPeriodDates(prev=>({...prev,[period]:next}));setDate(next);clear();setCategory('all')}
 function openDailyBoard(day:DailyBoard){setPeriod('daily');setDailyScope('top');setCategory('all');clear();setDate(day.source==='latest'?'latest':day.source==='snapshot'?day.captureDate!:'history:'+day.date)}
 return <><a className="skip-link" href="#main">跳到主要内容</a><header className="masthead"><div className="header-inner"><a className="brand" href={boardHref}><span className="brand-mark"><Radar size={23}/></span><strong>AI Radar<span>开源趋势观察</span></strong></a><nav aria-label="主导航"><a href="#/" aria-current={!isGithub&&!full&&!methodology&&!showingSpotlights?'page':undefined}>发现榜单</a><a href="#/github" aria-current={isGithub&&!full&&!methodology?'page':undefined}>GitHub 总榜</a><a href="#/spotlights" aria-current={showingSpotlights?'page':undefined}>有趣项目</a><a href={aboutHref} aria-current={methodology?'page':undefined}>数据说明</a></nav><a className="github-top" href={repoUrl} target="_blank" rel="noreferrer"><Github size={18}/><span>GitHub</span><ArrowUpRight size={14}/></a></div></header>
 {!data?<main id="main" className="loading-screen" role="status"><Radar size={38}/><h1>{error||'正在读取最新榜单'}</h1><p>官方数据，真实趋势。</p>{error&&<button className="primary-button" onClick={()=>window.location.reload()}>重新加载</button>}</main>:<main id="main" className="page">
 {error&&<div className="notice warning" role="alert">{error} 当前保留上一次已加载的榜单。</div>}
 {showingSpotlights?<Spotlights projects={data.projects}/>:methodology?<><a href={boardHref} className="back-link"><ArrowLeft size={16}/>返回榜单</a><article className="methodology"><span className="eyebrow">THE METHODOLOGY</span><h1>先看懂数字，再判断趋势。</h1><p className="lead">榜单衡量开源项目获得的关注，不直接代表产品质量或实际用户规模。</p><section><h2>年、月、周、日与历史总榜</h2><div className="method-grid">{periods.map(p=><div key={p.id}><p.icon size={22}/><h3>{p.label}</h3><p>{p.id==='custom'?'自行选择起止日期，汇总区间内每日 TOP 30，去重并合计上榜日新增 Star；不改变其他榜单周期。':p.id==='daily'?(isGithub?'最近已结束的来源统计日；仅纳入 Star 历史完整的项目，覆盖不足时显示部分榜单。':'最近已结束的来源统计日；覆盖不足时显示部分榜单，仅纳入指标完整的项目。'):p.id==='weekly'?'所选自然周内每天日榜 TOP 30 去重，合计各项目上榜日的新增 Star。':p.id==='monthly'?'所选自然月内每天日榜 TOP 30 去重，合计各项目上榜日的新增 Star。':p.id==='yearly'?'来源日期所在自然年，从年初到最近结束的统计日。':'最近成功采集的累计 Star，反映项目长期关注度。'}</p></div>)}</div></section><section><h2>数据从哪里来</h2><p>累计 Star、Fork、语言、许可证来自 GitHub 官方仓库 API。日、周、月、年榜依据官方 Star 历史接口返回的每日统计，未与 Trending 页面数字混排。Trending 和多组主题搜索仅用于发现候选项目。</p><p>{data.timezoneNote}</p><a href="https://docs.github.com/en/rest/activity/starring#get-repository-star-history" target="_blank" rel="noreferrer">阅读 GitHub 官方接口说明 <ExternalLink size={14}/></a></section><section><h2>缺失数据，不等于零</h2><p>只有时间窗口内的日数据完整时，项目才进入相应增长榜。失败项目保留上次记录并显示更新状态。我们不外推缺失增长，不用累计 Star 代替日增长，不把第三方推荐排名当作官方榜单。</p><p>当前收录 {data.bootstrapStats?.projectCount??data.projects.length} 个项目，其中 {data.listComplete?allRanked.length:data.bootstrapStats?.rankedDaily??allRanked.length} 个进入当前榜单。{data.scope}</p></section><section><h2>分类与详细介绍</h2>{isGithub?<p>总榜按仓库简介和 Topics 做初步方向分类，未经逐项人工核对。中文简介根据 GitHub 原始简介整理并标记待复核，详情保留原文供核对；来源变化时暂时显示待整理，不沿用过期说明。暂无可靠资料时不补写能力和使用条件。</p>:<p>项目按主要用途设置主分类，关联方向只标记实际具备的能力。项目形态区分应用、框架、模型、开发工具、技能、MCP 服务、学习资源、研究实现、数据集与协议；标签补充具体功能，使用方式合并同义名称。通用软件仅能被 AI 调用或宣传中提及 AI，不作为收录依据。已整理的中文解读基于项目文档；未完成中文解读的项目显示明确标注的作者原始简介；README 摘录保留原始语言供核对。自动分类会单独标记待复核，不把关键词匹配描述为功能验证。</p>}</section><section><h2>日榜的在榜时间</h2><p>从本站可回溯的最早日期起，按每天全站日榜前 30 名累计上榜日数，跨月、掉榜后重返仍继续累加，同一来源日期只计 1 天。已保存的日榜使用真实快照；更早的日期按当前收录项目的官方 Star 历史重算，因此回溯部分不等同于当时实际保存的榜单。分类和搜索筛选不改变该值；所有榜单项目行均显示截至所选统计日的累计记录。</p></section><section><h2>补充的历史回溯数据</h2><p>历史回溯从官方 Star 历史日值重算过去日期的日、周、月、年增长，可通过自定义时间选择起止日期，独立查看区间榜单。比较范围是当前收录项目，分类与介绍也使用当前资料。它不是当时保存的 GitHub Trending 或本站快照，存在当前收录范围带来的偏差。</p><p>回溯页不展示当时累计 Star；累计在榜天数包含按当前收录范围重算的历史日榜，缺少完整时间窗口的项目不参加相应增长排名。真实归档继续单独保留。</p></section><section><h2>每日更新与历史记录</h2><p>{isGithub?'总榜采用独立候选队列和独立采集文件，随 GitHub Actions 定时分批更新。':'AI 榜单按小时分批更新。'}平台定时任务可能延迟。每日归档先记录实际采集覆盖率，覆盖继续提高时更新；达到完整门槛后固定。历史快照保留对应采集时的排名与统计；页面中的项目介绍和分类同步采用最新整理内容。</p><p>最近完成：{when(data.completedAt)}（北京时间）。采集批次：{data.status==='complete'?'完成':'部分完成'}。</p><a href={repoUrl+'/actions'} target="_blank" rel="noreferrer">查看真实运行记录 <ExternalLink size={14}/></a></section></article></>:full?(project?<><a href={boardHref} className="back-link"><ArrowLeft size={16}/>返回榜单</a><div className="detail-layout"><article>{period==='custom'&&customRange&&<section className="notice"><strong>自定义区间 · {customRange.start} — {customRange.end}</strong><p>整段区间新增（含未上榜日）：{project.customGrowth==null?'数据不足':'+'+format(project.customGrowth)}</p></section>}{aggregated&&weeklyById.has(project.id)&&<section className="notice" aria-label="所选周期日榜贡献"><h2>{aggregateLabel}日榜汇总</h2><p>{weeklyBoard?.start} — {weeklyBoard?.end} · 上榜 {weeklyById.get(project.id)!.appearances} 天 · 日榜新增合计 +{format(weeklyById.get(project.id)!.growth)}</p><ul>{weeklyById.get(project.id)!.contributions.map(c=><li key={c.date}>{c.date} · 日榜第 {c.rank} 名 · 新增 +{format(c.growth)} Star</li>)}</ul></section>}<div className="detail-intro"><div className="detail-owner"><span className="repo-avatar large">{project.owner.slice(0,2).toUpperCase()}</span><span>{project.owner}<span className="muted"> / </span></span><a href={project.url} target="_blank" rel="noreferrer" aria-label="打开 GitHub 仓库"><Github size={22}/></a></div><h1>{project.name}</h1><p className="detail-summary">{project.summary}</p>{project.profileStatus==='generated'&&<p className="notice warning">这份中文介绍由 AI 根据仓库资料自动整理，尚待人工复核。具体能力、安装条件和适用范围请以官方文档为准。</p>}<div className="tags"><button className="category-tag" style={{color:color[project.category]}} onClick={()=>{setCategory(project.category);window.location.hash=boardHref}}>{categoryLabel(project.category)}</button><span className="kind-tag">{project.kind}</span>{project.profileStatus==='generated'&&<span className="warning-tag">AI 整理 · 待复核</span>}{project.archived&&<span className="warning-tag">已归档</span>}{project.tags.map(t=><button onClick={()=>selectTag(t)} key={t}>{t}</button>)}</div></div><div className="detail-metrics">{[{label:retrospective?'当前累计 Star':'累计 Star',value:format(project.stars)},{label:'日新增',value:project.metrics.daily===null?'待积累':'+'+format(project.metrics.daily)},{label:period==='weekly'?'整周新增（含未上榜日）':'周新增',value:project.metrics.weekly===null?'待积累':'+'+format(project.metrics.weekly)},{label:period==='monthly'?'整月新增（含未上榜日）':'月新增',value:project.metrics.monthly===null?'待积累':'+'+format(project.metrics.monthly)},{label:'年新增',value:project.metrics.yearly===null?'待积累':'+'+short(project.metrics.yearly)}].map(m=><div key={m.label}><span>{m.label}</span><strong>{m.value}</strong></div>)}</div>{project.warnings.length>0&&<div className="notice warning">{project.warnings.join(' · ')}</div>}<section className="detail-section"><span className="section-number">01 / OVERVIEW</span><h2>它解决什么问题</h2><p>{project.overview}</p>{project.useCases?.length? <><h3>可以用在哪些场景</h3><ul className="detail-list">{project.useCases.map(item=><li key={item}>{item}</li>)}</ul></>:null}<h3>适合谁使用</h3><p>{project.audience}</p>{project.features.length>0&&<><h3>核心能力</h3><div className="feature-list">{project.features.map(f=><span key={f}><Check size={16}/>{f}</span>)}</div></>}</section><HistoryChart project={project}/><section className="detail-section"><span className="section-number">02 / GET STARTED</span><h2>如何开始使用</h2><p>{project.usage}</p>{project.gettingStarted?.length?<ol className="getting-started">{project.gettingStarted.map(item=><li key={item}>{item}</li>)}</ol>:null}{project.requirements?.length?<><h3>准备条件</h3><ul className="detail-list">{project.requirements.map(item=><li key={item}>{item}</li>)}</ul></>:null}<div className="tags">{project.ways.length?project.ways.map(w=><span key={w}>{w}</span>):<span>具体运行方式待核实</span>}</div><h3>使用前了解</h3><p>{project.caveat}</p><div className="detail-actions"><a className="primary-button" href={project.url} target="_blank" rel="noreferrer"><Github size={17}/>查看 GitHub 仓库<ArrowUpRight size={16}/></a><a className="secondary-button" href={project.readmeUrl} target="_blank" rel="noreferrer">官方 README <ArrowUpRight size={16}/></a></div></section><section className="detail-section"><span className="section-number">03 / FROM THE SOURCE</span><h2>原始资料</h2>{isGithub&&project.description&&<><h3>GitHub 原始简介</h3><p>{project.description}</p></>}<h3>README 原文摘录</h3><p className="muted">保持原始语言。下文为文字节选，完整代码、图片及安装步骤请阅读官方文档。</p><div className="readme-excerpt">{project.readme?project.readme.split('\n\n').slice(0,12).map((p,i)=><p key={i}>{p}</p>):detailError?<p>{detailError}，请刷新页面重试。</p>:project.readme===undefined&&!detail?<p role="status">正在读取 README…</p>:<p>本次未读取到 README，请访问原始仓库查看。</p>}</div><a href={project.readmeUrl} target="_blank" rel="noreferrer">阅读完整文档 <ArrowUpRight size={14}/></a></section></article><aside className="detail-aside"><div className="aside-panel"><h2>项目档案</h2><dl>{[['累计在榜天数',boardTime(project)],['主要语言',project.language],['许可证',project.license==='NOASSERTION'?'非标准许可，需查原文':project.license],['Fork',format(project.forks)],['创建日期',project.createdAt.slice(0,10)],['代码更新',project.pushedAt.slice(0,10)],['首次收录',project.firstSeen],['维护状态',project.archived?'已归档':'未归档'],['数据更新',when(project.fetchedAt)]].map(([k,v])=><div key={k}><dt>{k}</dt><dd>{v}</dd></div>)}</dl>{project.homepage&&<a className="secondary-button full-width" href={project.homepage} target="_blank" rel="noreferrer">项目官方主页 <ExternalLink size={14}/></a>}</div><div className="aside-panel"><h2>分类依据</h2><p>{project.classificationBasis}</p>{project.profileStatus==='generated'&&<p>项目介绍状态：AI 自动整理，待人工复核</p>}{project.reviewedAt&&<p>当前项目介绍 · 整理于 {project.reviewedAt}</p>}{project.related.length>0&&<><h3>关联方向</h3><div className="tags">{project.related.map(c=><button key={c} onClick={()=>{setCategory(c);window.location.hash=boardHref}}>{categoryLabel(c)}</button>)}</div></>}<h3>GitHub Topics</h3><div className="tags subtle">{project.topics.slice(0,12).map(t=><span key={t}>{t}</span>)}</div></div><div className="aside-note"><ShieldCheck size={20}/><p>{retrospective?`增长数据回溯至 ${data.date}，介绍、分类及累计 Star 使用 ${data.metadataDate} 的当前资料。`:`排名与统计截至 ${data.periodEnd} 来源统计日（${data.date} 采集，${archivedView?'历史快照':'最新数据'}），项目介绍采用当前整理内容。`}官方历史统计与累计 Star 的净变化是不同指标。</p></div></aside></div></>:<div className="empty"><h1>这份快照中没有该项目</h1><a href={boardHref}>返回榜单</a></div>):<>
 <section className="intro"><div><span className="eyebrow"><span className="tiny-dot"/> {isGithub?'GITHUB REPOSITORY INDEX':'GITHUB AI INDEX'}</span><h1>{isGithub?'发现 GitHub 上值得关注的开源项目':'发现下一个值得关注的 AI 项目'}<span className="heading-dot">.</span></h1><p>{isGithub?'独立追踪各领域开源仓库的关注度与增长。':'追踪开源社区的真实增长，从热度中找到方向。'}</p></div><div className="update-status"><span><span className={`status-dot ${outdated?'late':''}`}/>{outdated?'更新延迟':data.pendingDay?'新统计日采集中':data.status==='partial'?'本期部分数据待更新':isGithub?'仓库资料已采集':'最近采集已完成'}</span><strong>{when(data.completedAt)}</strong><small>北京时间 · 按小时分批更新</small></div></section>
 <div className="stats-strip"><div><Database size={17}/><span>收录项目</span><strong>{format(data.bootstrapStats?.projectCount??data.projects.length)}</strong></div><div><Layers3 size={17}/><span>{isGithub?'项目方向':'应用方向'}</span><strong>{data.categories.length}</strong></div><div><TrendingUp size={17}/><span>可回溯日期</span><strong>{historyIndex?`${historyIndex.dates.length} 天`:'读取中'}</strong></div><a href={aboutHref}>数据来源与统计口径 <ArrowUpRight size={15}/></a></div>
 {outdated&&!archivedView&&<div className="notice warning">最新数据距今超过 36 小时。请查看 <a href={repoUrl+'/actions'} target="_blank" rel="noreferrer">采集运行记录</a>，当前仍展示最后一次有效结果。</div>}
 {data.pendingDay&&!archivedView&&<div className="notice warning" role="status">{isGithub?'GitHub 总榜':'AI 榜单'}：{data.pendingDay} 的日统计已覆盖 {format(data.pendingDayCoverage??0)} / {format(data.pendingDayTotal??0)} 个符合该日期条件的已收录项目，尚未达到日榜发布门槛。当前显示 {data.periodEnd} 日榜；新日期达到足够覆盖后自动切换。</div>}
 {!archivedView&&data.coverage&&data.coverage.pendingUpdates>0&&<div className="notice warning" role="status">{data.periodEnd} 的本期数据仅完成 {format(data.coverage.updatedRepositories)} / {format(data.coverage.trackedRepositories)} 个已收录项目；当前日榜为部分榜单，未更新项目不参榜，排名可能随补采变化。</div>}
 {archivedView&&!retrospective&&!archiveReady(data.coverage)&&<div className="notice warning" role="status">这份 {data.periodEnd} 归档{data.coverage?`仅完成 ${format(data.coverage.updatedRepositories)} / ${format(data.coverage.trackedRepositories)} 个项目的日统计`:'没有完整的采集覆盖记录'}，仅作采集记录；其排名不代表完整日榜。请通过日期选择查看按官方历史重算的日榜。</div>}
 {retrospectiveCoverage&&!archiveReady({trackedRepositories:retrospectiveCoverage.eligible,updatedRepositories:retrospectiveCoverage.complete})&&<div className="notice warning" role="status">所选回溯周期仅有 {format(retrospectiveCoverage.complete)} / {format(retrospectiveCoverage.eligible)} 个项目具备完整官方日统计。当前排名只包含数据完整的项目，不能视为全部收录项目的完整榜单。</div>}
  {!retrospective&&!archivedView&&data.coverage&&<p className="notice">已发现 {format(data.coverage.discoveredRepositories)} 个仓库 · 已收录 {format(data.coverage.trackedRepositories)} 个 · 待核验 {format(data.coverage.pendingCandidates)} 个 · {data.coverage.sourceDate} 本期数据完整 {format(data.coverage.updatedRepositories)} 个。{isGithub?'按跨主题搜索与 Trending 持续扩充；待更新指标不参榜。':'仅考虑累计至少 10 Star 的仓库，符合条件的项目不设总量上限；待更新指标不参榜。'}</p>}
  {(data.status==='partial'||data.warnings.length>0)&&<div className="notice warning">本批次部分来源或项目采集未完成。{data.warnings.length>0&&`${data.warnings.map(warning=>warning.replace(/[。；]+$/u,'')).join('；')}。`}{data.failedRepositories.length>0&&` ${data.failedRepositories.length} 个项目保留上次记录。`}</div>}
  {!isGithub&&<section className="discovery-teaser"><Sparkles size={20}/><div><h2>有趣项目</h2><p>从热门作品到新奇玩法，看看它能做什么、从哪里开始。</p></div><a href="#/spotlights">去看看 <ArrowUpRight size={15}/></a></section>}
 <div className="workspace"><div className="ranking-surface"><div className="ranking-toolbar"><Tabs value={period} onValueChange={v=>changePeriod(v as BoardPeriod)}><TabsList variant="line" className="period-tabs">{periods.map(p=><TabsTrigger key={p.id} value={p.id}><p.icon size={17}/>{p.label}</TabsTrigger>)}</TabsList></Tabs></div>
 {(period==='daily'||period==='weekly'||period==='monthly'||period==='yearly')&&historyIndex?.start&&historyIndex.end&&<PeriodSelector period={period} min={historyIndex.start} max={bootstrapData?.periodEnd??historyIndex.end} end={date.startsWith('history:')?date.slice(8):date==='latest'?bootstrapData?.periodEnd??historyIndex.end:data.periodEnd} onChange={choosePeriodEnd}/>}
 {period==='custom'&&(historyIndex?.start&&historyIndex.end?<CustomTimeRange key={customRange?customRange.start+customRange.end:'initial'} min={historyIndex.start} max={bootstrapData?.periodEnd??historyIndex.end} value={customRange} onApply={setCustomRange}/>:<p role="status">正在读取可选日期…</p>)}
 {period==='custom'&&customError&&<p className="notice warning" role="alert">{customError}<button onClick={()=>setCustomRange(customRange?{...customRange}:null)}>重新加载</button></p>}
 {retrospective&&period!=='custom'&&<div className="notice history-notice"><strong>历史回溯 · {data.periodStarts[period==='all'?'daily':period]} — {data.periodEnd}</strong><p>按官方日数据重算当前收录项目的增长；分类与介绍为当前资料。当时累计 Star 无法还原；累计在榜天数包含按当前收录范围重算的历史日榜。</p><button onClick={home}>返回最新日榜</button></div>}
 {aggregated&&(period!=='custom'||customReady)&&<section className="notice" aria-label={aggregateLabel+'汇总来源'}>
 <strong>{aggregateLabel} = 所选周期每天日榜 TOP 30 去重汇总</strong>
 <p>仅合计项目上榜当天的新增 Star，未上榜日和所选周期以外的数据不计入。累计 Star 不影响排序。</p>
 {weeklyError||boardHistoryError?<p role="alert">{weeklyError||boardHistoryError}<button type="button" onClick={()=>{dataCache.clear();setDataVersion(Date.now().toString())}}>重新读取日榜</button></p>:!weeklyBoard||weeklyLoading?<p role="status">正在汇总每日榜单…</p>:<><p>{weeklyBoard.start} — {weeklyBoard.end}：{weeklyBoard.days.reduce((n,d)=>n+d.rows.length,0)} 条日榜记录，去重后 {weeklyBoard.rows.length} 个项目。{weeklyBoard.retrospectiveDays>0&&`${weeklyBoard.retrospectiveDays} 天缺少覆盖充分的已存日榜，以官方每日统计回溯 TOP 30，并非当时保存的榜单。`}{weeklyBoard.unavailableDays>0&&`${weeklyBoard.unavailableDays} 天日榜不可用，目前是部分汇总，缺失不补零。`}</p>
 <details><summary>逐日核对汇总来源</summary><div className="archive-fields">{weeklyBoard.days.map(day=><button key={day.date} type="button" disabled={day.source==='unavailable'} onClick={()=>openDailyBoard(day)} aria-label={`查看 ${day.date} ${day.source==='snapshot'?'已存日榜':day.source==='retrospective'?'回溯日榜':'最新日榜'}`}>{day.date.slice(5)} · {day.source==='snapshot'?'已存日榜':day.source==='retrospective'?'日榜回溯':day.source==='latest'?'最新日榜':'日榜缺失'} · {day.rows.length} 项</button>)}</div></details></>}
 </section>}
 {period==='daily'&&<div className="daily-scope"><div className="scope-buttons"><button aria-pressed={dailyScope==='top'} onClick={()=>setDailyScope('top')}>日榜精选 TOP 30</button><button aria-pressed={dailyScope==='all'} onClick={()=>setDailyScope('all')}>全部项目数据</button></div><p>{data.periodEnd}：{data.listComplete?allRanked.filter(p=>(p.metrics.daily??0)>0).length:data.bootstrapStats?.positiveDaily??0} 个项目有增长，{data.listComplete?allRanked.filter(p=>p.metrics.daily===0).length:data.bootstrapStats?.zeroDaily??0} 个为零。精选展示收录范围内增长前 30 名，并非当天新建的项目。</p></div>}<div className="category-filters" aria-label="按应用方向筛选"><button aria-pressed={category==='all'} onClick={()=>setCategory('all')}>全部方向</button>{data.categories.map(c=><button key={c.id} aria-pressed={category===c.id} onClick={()=>setCategory(c.id)}><span className="category-dot" style={{background:color[c.id]}}/>{c.label}</button>)}</div>
 <div className="search-row"><label className="search-field"><Search size={18}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="搜索项目、用途或标签…" aria-label="搜索项目、用途或标签"/>{search&&<button onClick={()=>setSearch('')} aria-label="清除搜索"><X size={15}/></button>}</label><Picker label="主要语言" value={language} onChange={setLanguage} items={[{value:'all',label:'全部语言'},...languages.map(l=>({value:l,label:l}))]}/><Picker label="项目形态" value={kind} onChange={setKind} items={[{value:'all',label:'全部形态'},...kinds.map(l=>({value:l,label:l}))]}/></div>
 <details className="advanced-filters" open={advancedOpen} onToggle={event=>setAdvancedOpen(event.currentTarget.open)}><summary>更多筛选{filterActive?' · 条件已启用':''}</summary><div><Picker label="运行方式" value={way} onChange={setWay} items={[{value:'all',label:'全部运行方式'},...ways.map(l=>({value:l,label:l}))]}/><Picker label="维护状态" value={maintenance} onChange={setMaintenance} items={[{value:'all',label:'全部维护状态'},{value:'unarchived',label:'未归档'},{value:'archived',label:'已归档'}]}/></div></details>
 {filterActive&&<div className="active-filters">{tag&&<button onClick={()=>setTag('')}>标签：{tag}<X size={13}/></button>}<button onClick={clear}>清除筛选<X size={13}/></button></div>}
 <div className="list-heading" id="ranking-heading" tabIndex={-1}><div><h2>{category==='all'?(period==='daily'?(retrospective?'历史日榜':archivedView?'归档日榜':'最新日榜'):aggregated?'日榜汇总'+aggregateLabel:'开源热榜'):categoryLabel(category)}<span>{selectedPeriod.en}</span></h2><p>{period==='custom'?(customRange?`${customRange.start} — ${customRange.end} · 日榜新增汇总（含起止日期）`:'选择起止日期后查看榜单'):period==='all'?`累计 Star · 截至 ${data.date}`:`${data.periodStarts[period]}${data.periodStarts[period]!==data.periodEnd?' — '+data.periodEnd:''} · ${aggregated?'日榜新增汇总':'官方历史统计'}`}{retrospective?' · 历史回溯':archivedView?' · 已存快照':''}</p></div><span aria-live="polite">{loading||awaitingBoard?'加载中…':`${filtered.length} 个项目`}</span></div>
 <p className="daily-tenure-note"><Clock3 size={13}/>累计在榜统计截至 {data.periodEnd}，从 {cumulativeChart?.start??'有效数据起点'} 起计；跨月、掉榜后重返继续累加。更早的日榜记录不完整。</p>
 <div className="column-heading"><span>排名 / 项目</span><span>{aggregated?'日榜上榜天数':retrospective?'当时累计':'累计 Star'}</span><span>{aggregated?'最佳日榜名次':'近 14 日'}</span><span>{aggregated?'日榜新增合计':period==='all'?'总 Star':'周期新增'}<ArrowDown size={12}/></span></div>
 <div className="project-list" aria-busy={loading||awaitingBoard}>{filtered.slice(paging.start,paging.end).map(p=>{const index=categoryRanked.findIndex(x=>x.id===p.id)+1;const global=allRanked.findIndex(x=>x.id===p.id)+1;const s=score(p,period)!;const weekly=weeklyById.get(p.id);return <article className="project-row" key={p.id}><span className={`rank-number rank-${index}`}>{String(index).padStart(2,'0')}</span><div className="repo-info"><div className="repo-title"><a href={projectHref+encodeURIComponent(p.fullName)}><span>{p.owner} / </span><strong>{p.name}</strong></a>{index<=3&&categoryRanked.length>=10&&<span className="top-label">TOP {index}</span>}</div><p>{p.overview}</p><div className="row-tags"><button className="category-tag" onClick={()=>setCategory(p.category)}><span style={{background:color[p.category]}} className="category-dot"/>{categoryLabel(p.category)}</button><span>{p.kind}</span>{p.profileStatus==='generated'&&<span className="warning-tag">AI 整理 · 待复核</span>}{p.tags.slice(0,2).map(t=><button key={t} onClick={()=>setTag(t)}>{t}</button>)}<span className="tenure-tag" title={`截至 ${data.periodEnd} 的全站日榜 TOP 30 累计上榜日数；仅计覆盖充分的记录`}><Clock3 size={11}/>{boardTime(p)}</span><span className="language"><i style={{background:color[p.category]}}/>{p.language}</span>{p.archived&&<span className="warning-tag">已归档</span>}{category!=='all'&&<span>全站 #{global}</span>}</div></div><div className="row-stars">{aggregated?<><CalendarDays size={14}/>{weekly?.appearances} 天</>:<><Star size={14}/>{retrospective?'—':short(p.stars)}</>}</div><div className="row-chart">{aggregated?<span>TOP {weekly?.bestRank}</span>:<MiniChart history={p.history}/>}</div><a className="row-growth" href={projectHref+encodeURIComponent(p.fullName)} aria-label={`查看 ${p.name}，${aggregated?'日榜新增合计':period==='all'?'总 Star':'周期新增'} ${format(s)}`}><strong>{period==='all'?'':'+'}{short(s)}</strong><span>{aggregated?'日榜合计':period==='all'?'累计关注':'Star'}<ArrowUpRight size={13}/></span></a></article>})}</div>
 {period==='custom'&&!customRange&&<div className="empty"><CalendarDays size={28}/><h3>选择时间，查看这段时间的热门项目</h3><p>只合计所选区间内的上榜日贡献，各榜单分别保留所选周期。</p></div>}
 {filtered.length===0&&!(period==='custom'&&(!customRange||customLoading||customError))&&!(aggregated&&(!weeklyBoard||weeklyLoading))&&<div className="empty"><Search size={28}/><h3>{noGithubGrowth?'Star 历史正在补采':'暂时没有符合条件的项目'}</h3><p>{noGithubGrowth?'当前可查看累计 Star 总榜；周期榜会在官方日统计补齐后显示。':'试试其他分类或清除筛选。缺少完整周期数据的项目不会混入增长榜。'}</p><button className="secondary-button" onClick={()=>{clear();setCategory('all');if(noGithubGrowth)setPeriod('all');else setDailyScope('all')}}>{noGithubGrowth?'查看历史总榜':'查看全部项目'}</button></div>}
 {boardReady&&<Pagination {...paging} total={filtered.length} pageSize={pageSize} onPage={changePage} onPageSize={changePageSize}/>}
 <p className="list-footnote"><CircleHelp size={14}/>{aggregated?'仅汇总所选周期的每日 TOP 30；同一项目多次上榜合并，未上榜日的增长不计入。':`${!data.listComplete&&period==='daily'?data.bootstrapStats?.missingDaily??0:data.projects.filter(p=>!p.stale&&score(p,period)===null).length} 个项目暂缺完整周期数据。累计热度可在历史总榜查看。`}</p></div>
 <aside className="trend-aside"><section className="pulse-panel"><div className="pulse-label"><Radio size={16}/> TREND PULSE <span>观察</span></div><h2>{counts[0]?`${counts[0].label}进入视野`:'等待更多趋势数据'}</h2><p>{counts[0]?`当前${selectedPeriod.label}前 ${leaders.length} 名中，${counts[0].count} 个项目以${counts[0].label}为主方向。`:'采集完成后，将根据真实榜单提供方向分布。'}</p><span className="pulse-note">基于当前榜单分布，不代表行业整体份额。</span></section><section className="aside-panel direction-panel"><div className="section-head"><h2>热门方向</h2><span>前 {leaders.length} 名</span></div>{counts.slice(0,6).map(c=><button key={c.id} aria-label={`筛选${c.label}，前20名中${c.count}个项目`} onClick={()=>setCategory(c.id)}><div><span><i style={{background:color[c.id]}}/>{c.label}</span><strong>{c.count}</strong></div><div className="bar-track"><span style={{width:`${c.count/Math.max(leaders.length,1)*100}%`,background:color[c.id]}}/></div></button>)}</section><section className="aside-panel spot-panel"><span className="eyebrow"><Sparkles size={14}/> PROJECT SPOTLIGHT</span><h2>不只看 Star，<br/>也看它能做什么。</h2><p>从用途、运行方式到使用门槛，每个项目都提供资料与原始来源。</p>{allRanked[0]&&<a href={projectHref+encodeURIComponent(allRanked[0].fullName)}>阅读 {allRanked[0].name} 解读<ArrowUpRight size={15}/></a>}</section><section className="aside-note"><ShieldCheck size={20}/><p>数据来自 GitHub 官方接口。排名仅覆盖本站收录项目；查看数据说明了解统计口径。</p><a href={aboutHref}>了解榜单规则 <ArrowUpRight size={14}/></a></section></aside></div></>}
 </main>}<footer className="footer"><a className="footer-brand" href={boardHref}><Radar size={18}/> AI Radar</a><p>关注开源趋势，做出自己的判断。</p><div><a href="#/spotlights">有趣项目</a><a href={aboutHref}>数据说明</a><a href={repoUrl} target="_blank" rel="noreferrer">开源代码 <ArrowUpRight size={13}/></a></div></footer></>
}
