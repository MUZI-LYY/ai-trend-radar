import type {Dataset,Project,Period} from './types';
import {weekStart,priorDay} from './ranking';
export interface HistoryIndex {years?:{year:string;start:string;end:string;projects:number;completeProjects:number;projectDays:number}[];start:string;end:string;dates:string[];source:string;scope:string;generatedAt:string}
export interface HistoryData {generatedAt:string;source:string;scope:string;projects:{id:number;fullName:string;createdAt:string;days:{date:string;stars:number}[]}[]}
export function historyTotal(days:Map<string,number>,start:string,end:string,createdAt:string):number|null {
 const first=createdAt.slice(0,10)>start?createdAt.slice(0,10):start;
 if(first>end)return null;
 let total=0;
 for(let date=end;date>=first;date=priorDay(date)) {const value=days.get(date);if(value===undefined)return null;total+=value}
 return total;
}
export function replayHistory(latest:Dataset,history:HistoryData,end:string):Dataset{
 const records=new Map(history.projects.map(p=>[p.id,p]));
 const starts={daily:end,weekly:weekStart(end),monthly:end.slice(0,7)+'-01',yearly:end.slice(0,4)+'-01-01'};
 const projects:Project[]=latest.projects.filter(p=>p.createdAt.slice(0,10)<=end).map(p=>{
  const raw=records.get(p.id);const days=(raw?.days??[]).filter(d=>d.date<=end);const values=new Map(days.map(d=>[d.date,d.stars]));
  const metrics=Object.fromEntries(Object.entries(starts).map(([period,start])=>[period,historyTotal(values,start,end,p.createdAt)])) as Record<Exclude<Period,'all'>,number|null>;
  return {...p,metrics,stale:false,history:days,historyStatus:days.length?'ok':'unavailable',warnings:days.length?[]:['未取得此项目对应日期的历史数据']};
 });
 return {...latest,date:end,periodEnd:end,periodStarts:starts,projects,viewType:'retrospective',metadataDate:latest.date,
  status:'complete',warnings:[],failedRepositories:[],scope:history.scope,metric:'官方日统计回溯计算'};
}

/** A separate inclusive interval ranking; never mutates the standard period data. */
export function replayRange(latest:Dataset,history:HistoryData,start:string,end:string):Dataset{
 const valid=(day:string)=>/^\d{4}-\d{2}-\d{2}$/.test(day)&&Number.isFinite(Date.parse(day))&&new Date(day).toISOString().slice(0,10)===day;
 if(!valid(start)||!valid(end)||start>end||end>latest.periodEnd)throw new Error('请选择有效的起止日期，结束日期不能晚于最新统计日。');
 const replay=replayHistory(latest,history,end);
 return {...replay,projects:replay.projects.map(project=>({...project,
  customGrowth:historyTotal(new Map(project.history.map(day=>[day.date,day.stars])),start,end,project.createdAt),
  history:project.history.filter(day=>day.date>=start),
 })),metric:'自定义区间新增 Star'};
}
