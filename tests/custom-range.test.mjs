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

const {prepareDailyRange}=await import(url((await compile('history')).replace("'./ranking'",JSON.stringify(ranking))));
const {aggregateDailyBoards}=await import(url((await compile('weekly')).replace("'./ranking'",JSON.stringify(ranking))));
const {dailyLeaders}=await import(ranking);
test('custom chart uses only daily TOP 30 contributions inside inclusive arbitrary boundaries',()=>{
 const dates=['2025-12-30','2025-12-31','2026-01-01','2026-01-02','2026-01-03'];
 const make=(id,values)=>({id,fullName:`o/${String(id).padStart(2,'0')}`,stars:id,createdAt:'2020-01-01',metrics:{daily:0,weekly:999999,monthly:999999},history:dates.map((date,i)=>({date,stars:values[i]}))});
 const data={periodEnd:'2026-01-02',capturedAt:'2026-01-03T00:00:00Z',projects:[make(1,[999999,200,0,1,999999]),...Array.from({length:30},(_,i)=>make(i+2,[999999,100,0,100,999999]))]};
 const board=aggregateDailyBoards(data,[],'retrospective',[],'custom','2025-12-31');
 assert.equal(board.days.length,3);assert.equal(board.rows.length,31);assert.equal(board.days[1].rows.length,0);
 assert.equal(board.rows.find(r=>r.project.id===1).growth,200);assert.equal(board.rows.reduce((n,r)=>n+r.growth,0),6100);
 assert.deepEqual(board.rows.find(r=>r.project.id===1).contributions.map(c=>c.date),['2025-12-31']);
 const shorter=aggregateDailyBoards(data,[],'retrospective',[],'custom','2026-01-02');
 assert.equal(shorter.rows.length,30);assert.ok(!shorter.rows.some(r=>r.project.id===1));
 for(const start of [undefined,'2026-01-03','2025-02-30'])assert.throws(()=>aggregateDailyBoards(data,[],'retrospective',[],'custom',start));
});
test('current-end custom chart exactly matches latest daily board, including ties and stale projects',()=>{
 const live={...latest,projects:[
  {...latest.projects[0],stars:1,stale:false,metrics:{daily:5}},
  {...latest.projects[1],stars:1000,stale:false,metrics:{daily:5}},
  {...latest.projects[2],stars:9999,stale:true,metrics:{daily:999}},
 ]};
 const source={...history,projects:live.projects.map(p=>({id:p.id,days:[{date:'2026-01-03',stars:2},{date:'2026-01-04',stars:999}]}))};
 const before=structuredClone({live,source});const prepared=prepareDailyRange(live,source,'2026-01-03','2026-01-04');
 const board=aggregateDailyBoards(prepared.boardData,[],prepared.anchor,[],'custom','2026-01-03');
 assert.deepEqual(board.days.at(-1).rows.map(r=>r.project.id),dailyLeaders(live.projects));
 assert.equal(board.days[0].rows.length,3); // A stale current fetch does not erase valid earlier history.
 assert.equal(board.days.at(-1).rows[0].growth,5);
 assert.deepEqual({live,source},before);
});
test('custom and monthly/weekly boards agree for identical dates; missing saved days stay missing',()=>{
 const data={periodEnd:'2026-09-08',capturedAt:'2026-09-09T00:00:00Z',projects:[{id:1,fullName:'o/a',createdAt:'2020-01-01',stars:1,metrics:{daily:4},history:[{date:'2026-09-07',stars:3},{date:'2026-09-08',stars:4}]}]};
 for(const [period,start] of [['weekly','2026-09-07'],['monthly','2026-09-01']]){
  const standard=aggregateDailyBoards(data,[],'latest',[],period);
  const custom=aggregateDailyBoards(data,[],'latest',[],'custom',start);
  assert.deepEqual(custom,standard);
 }
 const saved={...data,date:'2026-09-08',capturedAt:'2026-09-08T00:00:00Z',periodEnd:'2026-09-07',projects:[{...data.projects[0],metrics:{daily:10}}]};
 assert.equal(aggregateDailyBoards(data,[saved],'latest',[],'custom','2026-09-07').rows[0].growth,14);
 assert.equal(aggregateDailyBoards(data,[],'latest',['2026-09-07'],'custom','2026-09-07').unavailableDays,1);
});
