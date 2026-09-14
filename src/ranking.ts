import type { Dataset, Project } from './types';
export interface BoardHistory {chartSize: number; entries: {date:string;capturedDate:string;ids:number[]}[]}
const dayMs=86400000;
export const priorDay=(day:string)=>new Date(Date.parse(day+'T00:00:00Z')-dayMs).toISOString().slice(0,10);
export function weekStart(day:string){const date=new Date(day+'T00:00:00Z');return new Date(date.getTime()-((date.getUTCDay()+6)%7)*dayMs).toISOString().slice(0,10)}
export function normalizeDataset(data:Dataset):Dataset {
 const start=weekStart(data.periodEnd);
 return {...data,periodStarts:{...data.periodStarts,weekly:start},projects:data.projects.map(p=>{
  if(p.metrics.weekly!==undefined)return p;
  const values=new Map(p.history.map(x=>[x.date,x.stars]));let total:number|null=p.stale||p.historyStatus!=='ok'?null:0;
  for(let date=data.periodEnd;date>=(p.createdAt.slice(0,10)>start?p.createdAt.slice(0,10):start)&&total!==null;date=priorDay(date)){
   const value=values.get(date);total=value===undefined?null:total+value;
  }
  return {...p,metrics:{...p.metrics,weekly:total}};
 })};
}
export function compareNames(a:string,b:string){const left=a.toLowerCase(),right=b.toLowerCase();return left<right?-1:left>right?1:0}
export function dailyLeaders(projects:Project[],limit=30){return projects.filter(p=>!p.stale&&(p.metrics.daily??0)>0).sort((a,b)=>b.metrics.daily!-a.metrics.daily!||b.stars-a.stars||compareNames(a.fullName,b.fullName)).slice(0,limit).map(p=>p.id)}
export function tenure(id:number,end:string,currentIds:number[],history:BoardHistory|null){
 if(!history)return null;
 if(!currentIds.includes(id))return {days:0,since:''};
 const entries=new Map<string,number[]>();for(const e of history.entries.slice().sort((a,b)=>a.capturedDate.localeCompare(b.capturedDate))){if(e.date<end&&!entries.has(e.date))entries.set(e.date,e.ids)}let since=end,days=1;
 while(entries.get(priorDay(since))?.includes(id)){since=priorDay(since);days++}
 return {days,since};
}
