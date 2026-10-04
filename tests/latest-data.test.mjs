import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';

const directory=await mkdtemp(join(tmpdir(),'radar-latest-data-'));
let completeLatest;
try {
 const source=await readFile(new URL('../src/latest-data.ts',import.meta.url),'utf8');
 const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
 await writeFile(join(directory,'latest-data.mjs'),compiled);
 ({completeLatest}=await import(pathToFileURL(join(directory,'latest-data.mjs'))));
} finally {await rm(directory,{recursive:true,force:true})}

test('list shards merge once and reject mixed publication versions',async()=>{
 const bootstrap={completedAt:'v1',listShardCount:16,bootstrapStats:{projectCount:2},projects:[{id:1}],listComplete:false};
 const cache=new Map();
 let calls=0;
 const get=async file=>{
  calls++;
  const index=Number(file.split('/').at(-1).replace('.json',''));
  return {completedAt:'v1',projects:index<2?[{id:index+1}]:[]};
 };
 const [first,second]=await Promise.all([
  completeLatest(bootstrap,get,cache),completeLatest(bootstrap,get,cache),
 ]);
 assert.equal(first,second);
 assert.deepEqual(first.projects.map(p=>p.id),[1,2]);
 assert.equal(first.listComplete,true);
 assert.equal(calls,bootstrap.listShardCount);
 const stale=async file=>({completedAt:file.endsWith('/0.json')?'v0':'v1',projects:[]});
 await assert.rejects(completeLatest(bootstrap,stale,new Map()),/榜单更新中/);
});
