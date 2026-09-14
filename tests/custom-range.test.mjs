import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import ts from 'typescript';

const compile=async name=>ts.transpileModule(await readFile(new URL(`../src/${name}.ts`,import.meta.url),'utf8'),{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
const url=source=>'data:text/javascript;base64,'+Buffer.from(source).toString('base64');
const ranking=url(await compile('ranking'));
const {replayRange}=await import(url((await compile('history')).replace("'./ranking'",JSON.stringify(ranking))));
const latest={date:'2026-01-05',periodEnd:'2026-01-04',periodStarts:{daily:'2026-01-04',weekly:'2025-12-29',monthly:'2026-01-01',yearly:'2026-01-01'},projects:[
 {id:1,fullName:'a/old',createdAt:'2020-01-01',metrics:{daily:99,weekly:199,monthly:299,yearly:399},history:[]},
 {id:2,fullName:'b/new',createdAt:'2026-01-01',metrics:{daily:1,weekly:1,monthly:1,yearly:1},history:[]},
 {id:3,fullName:'c/future',createdAt:'2026-01-03',metrics:{daily:1,weekly:1,monthly:1,yearly:1},history:[]},
]};
const history={scope:'Current tracked projects',projects:[
 {id:1,days:[{date:'2025-12-30',stars:900},{date:'2025-12-31',stars:2},{date:'2026-01-01',stars:3},{date:'2026-01-02',stars:5},{date:'2026-01-03',stars:800}]},
 {id:2,days:[{date:'2026-01-01',stars:0},{date:'2026-01-02',stars:7}]},
]};

test('custom range includes both boundaries across years and excludes later projects',()=>{
 const result=replayRange(latest,history,'2025-12-31','2026-01-02');
 assert.deepEqual(result.projects.map(p=>[p.id,p.customGrowth]),[[1,10],[2,7]]);
 assert.deepEqual(result.projects[0].history.map(d=>d.date),['2025-12-31','2026-01-01','2026-01-02']);
});
test('same-day zero is valid and missing days never become zero',()=>{
 assert.equal(replayRange(latest,history,'2026-01-01','2026-01-01').projects[1].customGrowth,0);
 const gaps=structuredClone(history);gaps.projects[0].days=gaps.projects[0].days.filter(d=>d.date!=='2026-01-01');
 assert.equal(replayRange(latest,gaps,'2025-12-31','2026-01-02').projects[0].customGrowth,null);
});
test('custom rankings leave all standard period values and sources untouched',()=>{
 const before=structuredClone({latest,history});
 replayRange(latest,history,'2025-12-31','2026-01-02');
 replayRange(latest,history,'2026-01-02','2026-01-03');
 assert.deepEqual({latest,history},before);
});
test('reversed, impossible, and unfinished source dates are rejected',()=>{
 for(const [start,end] of [['2026-01-02','2026-01-01'],['2025-02-30','2026-01-01'],['2026-01-01','2026-01-05']]){
  assert.throws(()=>replayRange(latest,history,start,end));
 }
});
