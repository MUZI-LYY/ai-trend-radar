import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
const directory=await mkdtemp(join(tmpdir(),'radar-history-'));
let replayHistory,historyTotal,compareNames,aggregateDailyBoards,dailyLeaders;
try {
 for(const module of ['ranking','history','weekly']) {
  const source=await readFile(new URL(`../src/${module}.ts`,import.meta.url),'utf8');
  const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace("'./ranking'","'./ranking.mjs'");
  await writeFile(join(directory,module+'.mjs'),compiled);
 }
 ({replayHistory,historyTotal}=await import(pathToFileURL(join(directory,'history.mjs')).href));
 ({compareNames,dailyLeaders}=await import(pathToFileURL(join(directory,'ranking.mjs')).href));
 ({aggregateDailyBoards}=await import(pathToFileURL(join(directory,'weekly.mjs')).href));
} finally {await rm(directory,{recursive:true,force:true})}
const latest=JSON.parse(await readFile(new URL('../public/data/latest.json',import.meta.url),'utf8'));
const historical=JSON.parse(await readFile(new URL('../public/data/history.json',import.meta.url),'utf8'));
test('historical replay agrees with source daily sums without changing actual metadata dates',()=>{
 const date='2025-12-31',result=replayHistory(latest,historical,date);
 assert.equal(result.viewType,'retrospective');assert.equal(result.metadataDate,latest.date);
 assert.equal(result.periodStarts.weekly,'2025-12-29');
 for(const p of result.projects){
  const source=historical.projects.find(x=>x.id===p.id);
  const days=source.days.filter(d=>d.date>='2025-01-01'&&d.date<=date);
  const first=p.createdAt.slice(0,10)>'2025-01-01'?p.createdAt.slice(0,10):'2025-01-01';
  const expectedCount=(Date.parse(date)-Date.parse(first))/86400000+1;
  const annual=days.length===expectedCount?days.reduce((n,d)=>n+d.stars,0):null;
  assert.equal(p.metrics.yearly,annual,p.fullName);
  assert.ok(p.history.every(d=>d.date<=date));assert.ok(p.createdAt.slice(0,10)<=date);
 }
});
test('missing data does not become zero or a complete week',()=>{
 assert.equal(historyTotal(new Map([['2025-01-01',5]]),'2024-12-30','2025-01-01','2020-01-01'),null);
 assert.equal(historyTotal(new Map([['2025-01-01',0]]),'2025-01-01','2025-01-01','2020-01-01'),0);
});
test('repositories not created on historical date do not enter replay rankings',()=>{
 const result=replayHistory(latest,historical,'2025-01-01');
 assert.ok(result.projects.length<latest.projects.length);
 assert.ok(result.projects.every(p=>p.createdAt.slice(0,10)<='2025-01-01'));
});
test('same-score repository sorting matches the Python collector',()=>{
 assert.equal(compareNames('o/a-b','o/a_b'),-1);assert.equal(compareNames('O/A','o/a'),0);
});

function weeklyProject(id,days,values={}) {
 return {id,fullName:`org/p${String(id).padStart(2,'0')}`,stars:id,createdAt:'2020-01-01T00:00:00Z',
  metrics:{daily:days['2026-09-08']??0,weekly:999999,monthly:999999,yearly:999999},
  history:Object.entries(days).map(([date,stars])=>({date,stars})),...values};
}
function weeklyData(projects,end='2026-09-08',values={}) {
 return {projects,periodEnd:end,date:'2026-09-09',capturedAt:'2026-09-09T00:00:00Z',...values};
}
test('weekly chart is daily TOP 30 union; only on-chart days contribute, never stored weekly totals',()=>{
 const target=weeklyProject(1,{'2026-09-06':999999,'2026-09-07':200,'2026-09-08':1,'2026-09-09':888888});
 const others=Array.from({length:30},(_,i)=>weeklyProject(i+2,{'2026-09-07':100,'2026-09-08':100}));
 const dormant=weeklyProject(99,{'2026-09-07':0,'2026-09-08':0},{stars:100000000});
 const data=weeklyData([target,...others,dormant]);const before=JSON.stringify(data);
 const board=aggregateDailyBoards(data,[]);
 assert.equal(board.rows.length,31);assert.equal(board.days.reduce((n,d)=>n+d.rows.length,0),60);
 const entry=board.rows.find(r=>r.project.id===1);
 assert.equal(entry.growth,200);assert.equal(entry.appearances,1);assert.equal(entry.bestRank,1);
 assert.deepEqual(entry.contributions.map(c=>c.date),['2026-09-07']);
 assert.ok(!board.rows.some(r=>r.project.id===99));
 assert.equal(board.rows.reduce((n,r)=>n+r.growth,0),6100);
 assert.equal(JSON.stringify(data),before);
});
test('saved daily chart wins over retrospective data and duplicate captures do not double count',()=>{
 const current=weeklyData([weeklyProject(1,{'2026-09-07':900,'2026-09-08':4},{fullName:'org/new-name'})]);
 const original=weeklyData([weeklyProject(1,{}, {fullName:'org/old-name',metrics:{daily:3}})],'2026-09-07',
  {date:'2026-09-08',capturedAt:'2026-09-08T00:00:00Z'});
 const later={...original,capturedAt:'2026-09-08T12:00:00Z',projects:[weeklyProject(1,{}, {metrics:{daily:999}})]};
 const board=aggregateDailyBoards(current,[later,original]);
 assert.equal(board.rows.length,1);assert.equal(board.rows[0].growth,7);
 assert.equal(board.rows[0].project.fullName,'org/new-name');assert.equal(board.rows[0].appearances,2);
 assert.equal(board.days[0].source,'snapshot');assert.equal(board.days[0].captureDate,'2026-09-08');
});
test('missing daily charts are explicit; complete zero days are valid empty charts',()=>{
 const missing=weeklyData([weeklyProject(1,{'2026-09-08':2})]);
 assert.equal(aggregateDailyBoards(missing,[]).unavailableDays,1);
 const zero=weeklyData([weeklyProject(1,{'2026-09-07':0,'2026-09-08':2})]);
 assert.equal(aggregateDailyBoards(zero,[]).unavailableDays,0);
 assert.equal(aggregateDailyBoards(zero,[]).days[0].rows.length,0);
 assert.equal(aggregateDailyBoards(zero,[], 'latest',['2026-09-07']).unavailableDays,1);
 assert.equal(aggregateDailyBoards(zero,[], 'snapshot').unavailableDays,1);
});
test('weekly boundaries cross a year without including an outside day or an unborn repository',()=>{
 const p=weeklyProject(1,{'2025-12-28':999,'2025-12-29':2,'2025-12-30':3,'2025-12-31':4,'2026-01-01':5,'2026-01-02':999},
  {metrics:{daily:5}});
 const unborn=weeklyProject(2,{'2025-12-29':10000},{createdAt:'2026-01-02T00:00:00Z'});
 const board=aggregateDailyBoards(weeklyData([p,unborn],'2026-01-01'),[]);
 assert.equal(board.start,'2025-12-29');assert.equal(board.days.length,4);
 assert.equal(board.rows.length,1);assert.equal(board.rows[0].growth,14);
});
test('historical daily ties use repository name; cumulative lifetime stars do not affect weekly ties',()=>{
 const a=weeklyProject(1,{'2026-09-07':5,'2026-09-08':5},{stars:1});
 const b=weeklyProject(2,{'2026-09-07':5,'2026-09-08':5},{stars:1000000});
 const board=aggregateDailyBoards(weeklyData([b,a]),[],'retrospective');
 assert.deepEqual(board.rows.map(r=>r.project.id),[1,2]);
 assert.deepEqual(board.days[0].rows.map(r=>r.project.id),[1,2]);
});
test('live weekly anchor matches the actual homepage daily TOP 30',()=>{
 const board=aggregateDailyBoards(latest,[]);
 assert.deepEqual(board.days.at(-1).rows.map(r=>r.project.id),dailyLeaders(latest.projects));
 const union=new Set(board.days.flatMap(d=>d.rows.map(r=>r.project.id)));
 assert.equal(board.rows.length,union.size);
 assert.ok(board.rows.length<=30*board.days.length);
});
