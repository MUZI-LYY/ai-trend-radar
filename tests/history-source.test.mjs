import {test} from 'node:test';
import assert from 'node:assert/strict';
import {gzipSync} from 'node:zlib';
import {readFile,writeFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {pathToFileURL} from 'node:url';
import ts from 'typescript';

const directory=await mkdtemp(join(tmpdir(),'radar-history-source-'));
let parseHistoryResponse;
try{
 const source=await readFile(new URL('../src/history-source.ts',import.meta.url),'utf8');
 const compiled=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.ES2022}}).outputText;
 await writeFile(join(directory,'history-source.mjs'),compiled);
 ({parseHistoryResponse}=await import(pathToFileURL(join(directory,'history-source.mjs'))));
}finally{await rm(directory,{recursive:true,force:true})}

test('compressed history and an already-decoded response produce the same records',async()=>{
 const history={projects:[{id:1,days:[{date:'2026-10-03',stars:4}]}]};
 const plain=Buffer.from(JSON.stringify(history));
 assert.deepEqual(await parseHistoryResponse(new Response(gzipSync(plain))),history);
 assert.deepEqual(await parseHistoryResponse(new Response(plain)),history);
});

test('corrupt compressed history cannot silently turn into empty data',async()=>{
 await assert.rejects(parseHistoryResponse(new Response(Buffer.from([0x1f,0x8b,1,2]))));
});
