import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';

const dir=await mkdtemp(join(tmpdir(),'radar-editorial-'));
let withLatestProfiles;
try {
 const source=await readFile(new URL('../src/editorial.ts',import.meta.url),'utf8');
 const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
 await writeFile(join(dir,'editorial.mjs'),compiled);
 ({withLatestProfiles}=await import(pathToFileURL(join(dir,'editorial.mjs'))));
} finally {await rm(dir,{recursive:true,force:true})}

test('historical profiles refresh by stable ID without changing history, metrics or membership',()=>{
 const old={id:42,fullName:'old/repo',stars:100,metrics:{daily:12,yearly:90},
  history:[{date:'2025-01-02',stars:12}],createdAt:'2020-01-01',fetchedAt:'2025-01-03',
  stale:true,editorial:false,overview:'旧介绍',category:'apps'};
 const removed={id:43,fullName:'old/removed',overview:'存档介绍'};
 const data={date:'2025-01-03',capturedAt:'2025-01-03T00:00:00Z',projects:[old,removed]};
 const latest={date:'2026-09-15',projects:[{...old,fullName:'new/name',stars:9999,
  metrics:{daily:99,yearly:9000},history:[],stale:false,editorial:true,overview:'完整中文介绍',
  category:'agents',reviewedAt:'2026-09-15',readme:'最新来源摘录'},
  {id:44,fullName:'new/project',editorial:true}]};
 const before=JSON.stringify({data,latest});
 const result=withLatestProfiles(data,latest);
 assert.deepEqual(result.projects.map(p=>p.id),[42,43]);
 assert.equal(result.projects[0].overview,'完整中文介绍');
 assert.equal(result.projects[0].reviewedAt,'2026-09-15');
 assert.equal(result.projects[0].category,'agents');
 for(const key of ['id','fullName','stars','metrics','history','createdAt','fetchedAt','stale']){
  assert.deepEqual(result.projects[0][key],old[key],key);
 }
 assert.equal(result.capturedAt,data.capturedAt);
 assert.equal(result.projects[1],removed);
 assert.equal(JSON.stringify({data,latest}),before);
});

test('an unreviewed latest profile never replaces a reviewed historical description',()=>{
 const data={projects:[{id:1,editorial:true,overview:'已整理介绍'}]};
 assert.equal(withLatestProfiles(data,{projects:[{id:1,editorial:false,overview:'自动提取'}]}).projects[0],data.projects[0]);
});

test('historical boards use the latest Chinese fallback for unreviewed projects',()=>{
 const old={id:2,editorial:false,overview:'README 原文：English text',stars:12,metrics:{daily:3}};
 const latest={id:2,editorial:false,overview:'项目用途待中文核对',stars:99,metrics:{daily:7}};
 const result=withLatestProfiles({projects:[old]},{projects:[latest]});
 assert.equal(result.projects[0].overview,latest.overview);
 assert.equal(result.projects[0].stars,old.stars);
 assert.deepEqual(result.projects[0].metrics,old.metrics);
});

test('historical boards carry the generated status from the latest profile',()=>{
 const old={id:3,editorial:false,overview:'旧介绍',stars:12,profileStatus:undefined};
 const latest={id:3,editorial:false,overview:'AI 整理的中文介绍',stars:88,
  profileStatus:'generated',classificationBasis:'AI 自动整理，待人工复核'};
 const result=withLatestProfiles({projects:[old]},{projects:[latest]});
 assert.equal(result.projects[0].overview,latest.overview);
 assert.equal(result.projects[0].profileStatus,'generated');
 assert.equal(result.projects[0].classificationBasis,latest.classificationBasis);
 assert.equal(result.projects[0].stars,old.stars);
});

test('generated latest profile does not downgrade a historical human review',()=>{
 const old={id:4,editorial:true,overview:'人工介绍',profileStatus:undefined};
 const latest={id:4,editorial:false,overview:'机器介绍',profileStatus:'generated'};
 assert.equal(withLatestProfiles({projects:[old]},{projects:[latest]}).projects[0],old);
});
