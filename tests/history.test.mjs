import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFile, writeFile, mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import ts from 'typescript';
const directory=await mkdtemp(join(tmpdir(),'radar-history-'));
let replayHistory,historyTotal,compareNames;
try {
 for(const module of ['ranking','history']) {
  const source=await readFile(new URL(`../src/${module}.ts`,import.meta.url),'utf8');
  const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replace("'./ranking'","'./ranking.mjs'");
  await writeFile(join(directory,module+'.mjs'),compiled);
 }
 ({replayHistory,historyTotal}=await import(pathToFileURL(join(directory,'history.mjs')).href));
 ({compareNames}=await import(pathToFileURL(join(directory,'ranking.mjs')).href));
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
