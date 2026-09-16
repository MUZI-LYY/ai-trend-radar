import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';
const directory=await mkdtemp(join(tmpdir(),'radar-board-'));
let parseBoardState,boardQueryKey,pageWindow,pageNumbers;
try {
 const source=await readFile(new URL('../src/board-state.ts',import.meta.url),'utf8');
 await writeFile(join(directory,'board-state.mjs'),ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText);
 ({parseBoardState,boardQueryKey,pageWindow,pageNumbers}=await import(pathToFileURL(join(directory,'board-state.mjs'))));
}finally{await rm(directory,{recursive:true,force:true})}
test('new or corrupt sessions open the daily board with ten rows',()=>{
 for(const raw of [null,'broken','null','[]']){
  const state=parseBoardState(raw);assert.equal(state.period,'daily');assert.equal(state.pageSize,10);assert.equal(state.page,1);
 }
 const state=parseBoardState(JSON.stringify({period:'unknown',page:-1,pageSize:30,date:'history:2025-02-30',customRange:{start:'2025-03-01',end:'2025-02-01'}}));
 assert.equal(state.date,'latest');assert.equal(state.customRange,null);assert.equal(state.pageSize,10);
});
test('a detail reload retains historical/custom periods, filters and pagination',()=>{
 const state={...parseBoardState(null),period:'custom',date:'history:2025-12-31',periodDates:{yearly:'history:2025-12-31',monthly:'history:2026-01-31'},customRange:{start:'2025-12-20',end:'2026-01-10'},search:'agent',category:'coding',language:'Python',kind:'框架 / SDK',tag:'RAG',way:'CLI',maintenance:'unarchived',dailyScope:'all',advancedOpen:true,page:3,pageSize:20};
 assert.deepEqual(parseBoardState(JSON.stringify(state)),state);
 assert.equal(boardQueryKey(state),boardQueryKey({...state,page:1,advancedOpen:false}));
 for(const [key,value] of [['search','other'],['pageSize',50],['date','latest'],['period','daily'],['category','all']])assert.notEqual(boardQueryKey(state),boardQueryKey({...state,[key]:value}));
});
test('pagination has no duplicates or omissions and bounds the final and empty pages',()=>{
 for(const size of [10,20,50]){
  const items=Array.from({length:107},(_,i)=>i);const visible=[];
  for(let page=1;page<=Math.ceil(items.length/size);page++){
   const range=pageWindow(items.length,page,size);visible.push(...items.slice(range.start,range.end));
  }
  assert.deepEqual(visible,items);
 }
 assert.deepEqual(pageWindow(21,9,10),{page:3,pages:3,start:20,end:21});
 assert.deepEqual(pageWindow(0,9,10),{page:1,pages:1,start:0,end:0});
 assert.deepEqual(pageNumbers(5,20),[1,'gap',3,4,5,6,7,'gap',20]);
 assert.deepEqual(pageNumbers(1,1),[1]);
});
