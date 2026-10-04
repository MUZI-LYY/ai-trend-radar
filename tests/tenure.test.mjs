import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';

const directory=await mkdtemp(join(tmpdir(),'radar-tenure-'));
let tenure;
try {
 const source=await readFile(new URL('../src/ranking.ts',import.meta.url),'utf8');
 const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
 await writeFile(join(directory,'ranking.mjs'),compiled);
 ({tenure}=await import(pathToFileURL(join(directory,'ranking.mjs'))));
} finally {await rm(directory,{recursive:true,force:true})}

test('daily chart days accumulate across months, gaps and re-entry',()=>{
 const history={chartSize:30,entries:[
  {date:'2026-09-29',capturedDate:'2026-09-30',ids:[1]},
  {date:'2026-09-30',capturedDate:'2026-10-01',ids:[1]},
  {date:'2026-09-30',capturedDate:'2026-10-02',ids:[1]},
  {date:'2026-10-01',capturedDate:'2026-10-02',ids:[2]},
  {date:'2026-10-02',capturedDate:'2026-10-03',ids:[1]},
 ]};
 assert.deepEqual(tenure(1,'2026-10-03',[1],history),{days:4,since:'2026-09-29'});
 assert.deepEqual(tenure(1,'2026-10-03',[2],history),{days:3,since:'2026-09-29'});
 assert.deepEqual(tenure(2,'2026-10-03',[1],history),{days:1,since:'2026-10-01'});
 assert.deepEqual(tenure(3,'2026-10-03',[1],history),{days:0,since:''});
});

test('current source day counts once even when already archived',()=>{
 const history={chartSize:30,entries:[
  {date:'2026-09-30',capturedDate:'2026-10-01',ids:[1]},
  {date:'2026-10-01',capturedDate:'2026-10-02',ids:[1]},
 ]};
 assert.deepEqual(tenure(1,'2026-10-01',[1],history),{days:2,since:'2026-09-30'});
 assert.deepEqual(tenure(1,'2026-10-01',[],history),{days:1,since:'2026-09-30'});
});
