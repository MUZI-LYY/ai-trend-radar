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
