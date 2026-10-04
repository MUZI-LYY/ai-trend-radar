import type {Dataset,Project} from './types';

export type DataGetter=<T,>(file:string)=>Promise<T>;

interface ListShard {completedAt:string;projects:Project[]}

export function completeLatest(bootstrap:Dataset,get:DataGetter,cache:Map<string,Promise<unknown>>):Promise<Dataset>{
 const key='latest-full';
 if(!cache.has(key)){
  const count=bootstrap.listShardCount;
  if(typeof count!=='number'||!Number.isSafeInteger(count)||count<1) return Promise.reject(Error('榜单分片索引无效，请重新加载。'));
  const promise=Promise.all(Array.from({length:count},(_,index)=>get<ListShard>(`latest-list/${index}.json`))).then(shards=>{
   if(shards.some(shard=>shard.completedAt!==bootstrap.completedAt))throw Error('榜单更新中，请重新加载。');
   const projects=shards.flatMap(shard=>shard.projects);
   if(projects.length!==bootstrap.bootstrapStats?.projectCount)throw Error('榜单分片不完整，请重新加载。');
   return {...bootstrap,projects,listComplete:true};
  }).catch(error=>{cache.delete(key);throw error});
  cache.set(key,promise);
 }
 return cache.get(key)! as Promise<Dataset>;
}
