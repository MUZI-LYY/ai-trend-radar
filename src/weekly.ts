import type {Dataset,Project} from './types';
import {compareNames,priorDay,weekStart} from './ranking';

export type DailySource='latest'|'snapshot'|'retrospective'|'unavailable';
export interface DailyBoardRow {project:Project;growth:number;rank:number}
export interface DailyBoard {
 date:string;source:DailySource;captureDate?:string;rows:DailyBoardRow[];missingProjects:number;
}
export interface WeeklyRow {
 project:Project;growth:number;appearances:number;bestRank:number;
 contributions:{date:string;growth:number;rank:number;source:DailySource}[];
}
export interface WeeklyBoard {
 start:string;end:string;days:DailyBoard[];rows:WeeklyRow[];
 retrospectiveDays:number;unavailableDays:number;
}

function dailyBoard(data:Dataset,date:string,source:DailySource,histories?:Map<number,Map<string,number>>):DailyBoard {
 const replay=source==='retrospective';
 const eligible=data.projects.filter(p=>p.createdAt.slice(0,10)<=date);
 const values=eligible.map(project=>({project,growth:replay?
  histories?.get(project.id)?.get(date):
  project.stale?undefined:project.metrics.daily}));
 const missingProjects=values.filter(p=>p.growth===undefined||p.growth===null).length;
 const available=values.filter((p):p is {project:Project;growth:number}=>typeof p.growth==='number');
 const rows=available.filter(p=>p.growth>0).sort((a,b)=>b.growth-a.growth||
  (replay?0:b.project.stars-a.project.stars)||compareNames(a.project.fullName,b.project.fullName))
  .slice(0,30).map((p,i)=>({...p,rank:i+1}));
 return {date,source:eligible.length>0&&available.length===0?'unavailable':source,
  captureDate:source==='snapshot'?data.date:undefined,rows,missingProjects};
}

/** Aggregate actual daily chart rows, never the repository-wide weekly metrics.
 * The anchor day's chart matches the selected daily view exactly. Older saved
 * charts are authoritative; unsaved days are visibly reconstructed from day data.
 * A project contributes only on days it entered that day's positive-growth TOP 30.
 */
export function aggregateDailyBoards(data:Dataset,snapshots:Dataset[],anchor:DailySource='latest',failedDates:string[]=[],period:'weekly'|'monthly'|'custom'='weekly',rangeStart?:string):WeeklyBoard {
 const end=data.periodEnd,start=period==='custom'?rangeStart!:period==='monthly'?end.slice(0,7)+'-01':weekStart(end);
 if(!start||!/^\d{4}-\d{2}-\d{2}$/.test(start)||!Number.isFinite(Date.parse(start))||new Date(start).toISOString().slice(0,10)!==start||start>end)throw Error('无效的日榜汇总起止日期');
 const histories=new Map(data.projects.map(p=>[p.id,new Map(p.history.map(d=>[d.date,d.stars]))]));
 const saved=new Map<string,Dataset>();
 for(const snapshot of [...snapshots].sort((a,b)=>a.capturedAt.localeCompare(b.capturedAt))) {
  if(snapshot.periodEnd<start||snapshot.periodEnd>end)continue;
  if(anchor==='snapshot'&&snapshot.capturedAt>data.capturedAt)continue;
  if(!saved.has(snapshot.periodEnd))saved.set(snapshot.periodEnd,snapshot);
 }
 const dates:string[]=[];
 for(let date=end;date>=start;date=priorDay(date))dates.unshift(date);
 const days=dates.map(date=>{
  if(date===end)return dailyBoard(data,date,anchor,histories);
  if(failedDates.includes(date))return {date,source:'unavailable' as const,rows:[],missingProjects:0};
  const snapshot=saved.get(date);
  if(snapshot)return dailyBoard(snapshot,date,'snapshot');
  if(anchor==='snapshot')return {date,source:'unavailable' as const,rows:[],missingProjects:0};
  return dailyBoard(data,date,'retrospective',histories);
 });
 const current=new Map(data.projects.map(p=>[p.id,p]));
 const byId=new Map<number,WeeklyRow>();
 for(const day of days)for(const row of day.rows) {
  let total=byId.get(row.project.id);
  if(!total){total={project:current.get(row.project.id)??row.project,growth:0,appearances:0,
   bestRank:row.rank,contributions:[]};byId.set(row.project.id,total)}
  total.growth+=row.growth;total.appearances+=1;total.bestRank=Math.min(total.bestRank,row.rank);
  total.contributions.push({date:day.date,growth:row.growth,rank:row.rank,source:day.source});
 }
 const rows=[...byId.values()].sort((a,b)=>b.growth-a.growth||compareNames(a.project.fullName,b.project.fullName));
 return {start,end,days,rows,retrospectiveDays:days.filter(d=>d.source==='retrospective').length,
  unavailableDays:days.filter(d=>d.source==='unavailable').length};
}
