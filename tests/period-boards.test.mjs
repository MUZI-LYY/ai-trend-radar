import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
const dir=await mkdtemp(join(tmpdir(),'radar-period-'));
let periodOptions,aggregateDailyBoards;
try{
 for(const name of ['ranking','weekly','period-options']){
  const source=await readFile(new URL(`../src/${name}.ts`,import.meta.url),'utf8');
  const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText.replaceAll("'./ranking'","'./ranking.mjs'");
  await writeFile(join(dir,name+'.mjs'),compiled);
 }
 ({periodOptions}=await import(pathToFileURL(join(dir,'period-options.mjs'))));
 ({aggregateDailyBoards}=await import(pathToFileURL(join(dir,'weekly.mjs'))));
}finally{await rm(dir,{recursive:true,force:true})}
test('monthly selectors include leap day, exclude future months and truncate current month',()=>{
 const options=periodOptions('monthly','2024-01-01','2024-03-12');
 assert.deepEqual(options.map(o=>[o.start,o.end]),[['2024-03-01','2024-03-12'],['2024-02-01','2024-02-29'],['2024-01-01','2024-01-31']]);
 assert.ok(options[0].label.includes('未结束'));
});
test('week selection uses ISO year and week across year boundary with no duplicate dates',()=>{
 const options=periodOptions('weekly','2025-12-28','2026-01-10');
 assert.deepEqual(options.map(o=>[o.year,o.start,o.end]),[['2026','2026-01-05','2026-01-10'],['2026','2025-12-29','2026-01-04'],['2025','2025-12-22','2025-12-28']]);
 assert.ok(options[1].label.startsWith('第 1 周'));
 const year=periodOptions('yearly','2024-01-01','2026-09-13');
 assert.deepEqual(year.map(o=>o.end),['2026-09-13','2025-12-31','2024-12-31']);
});
test('monthly chart unions each daily TOP 30, excludes outside month and off-chart contributions',()=>{
 const dates=['2024-01-31','2024-02-01','2024-02-02','2024-02-03'];
 const project=(id,values)=>({id,fullName:`o/${String(id).padStart(3,'0')}`,createdAt:'2020-01-01',stars:999999,stale:false,metrics:{daily:0,monthly:999999},history:dates.map((date,i)=>({date,stars:values[i]}))});
 const projects=[project(1,[999999,200,1,999999]),...Array.from({length:30},(_,i)=>project(i+2,[999999,100,100,999999]))];
 const data={projects,periodEnd:'2024-02-02',date:'2024-02-02',capturedAt:'2024-02-03T00:00:00Z'};
 const before=JSON.stringify(data),board=aggregateDailyBoards(data,[],'retrospective',[],'monthly');
 assert.equal(board.start,'2024-02-01');assert.equal(board.days.length,2);assert.equal(board.rows.length,31);
 assert.equal(board.rows.find(r=>r.project.id===1).growth,200);
 assert.equal(board.rows.find(r=>r.project.id===1).appearances,1);
 assert.equal(board.rows.reduce((n,r)=>n+r.growth,0),6100);assert.equal(JSON.stringify(data),before);
});
test('month closes exactly at leap day and preserves missing daily sources',()=>{
 const data={projects:[{id:1,fullName:'a/a',createdAt:'2020-01-01',history:[{date:'2024-02-29',stars:2}],metrics:{daily:2}}],periodEnd:'2024-02-29',capturedAt:'2024-03-01T00:00:00Z'};
 const board=aggregateDailyBoards(data,[],'retrospective',[],'monthly');
 assert.equal(board.days.length,29);assert.equal(board.unavailableDays,28);assert.equal(board.rows[0].growth,2);
});
