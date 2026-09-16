import type {Period} from './types';
export type BoardPeriod = Period | 'custom';
export const boardStateKey = 'ai-radar:board:v1';
export const pageSizes = [10,20,50] as const;
export type PageSize = typeof pageSizes[number];
export interface BoardState {
 period:BoardPeriod; category:string; search:string; language:string; kind:string;
 tag:string; way:string; maintenance:string; date:string; dailyScope:'top'|'all';
 periodDates:Partial<Record<BoardPeriod,string>>;
 customRange:{start:string;end:string}|null; advancedOpen:boolean; page:number; pageSize:PageSize;
}
export const defaultBoardState:BoardState={period:'daily',category:'all',search:'',language:'all',kind:'all',tag:'',way:'all',maintenance:'all',date:'latest',dailyScope:'top',periodDates:{},customRange:null,advancedOpen:false,page:1,pageSize:10};
const periods:BoardPeriod[]=['daily','weekly','monthly','yearly','all','custom'];
const validDay=(value:unknown):value is string=>typeof value==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(value)&&Number.isFinite(Date.parse(value))&&new Date(value).toISOString().slice(0,10)===value;
const validDate=(value:unknown):value is string=>value==='latest'||validDay(value)||(typeof value==='string'&&value.startsWith('history:')&&validDay(value.slice(8)));
export function parseBoardState(raw:string|null):BoardState {
 const state={...defaultBoardState,periodDates:{}} as BoardState;
 try {
  const value=JSON.parse(raw??'null');if(!value||typeof value!=='object')return state;
  if(periods.includes(value.period))state.period=value.period;
  for(const key of ['category','search','language','kind','tag','way'] as const)if(typeof value[key]==='string')state[key]=value[key];
  if(['all','archived','unarchived'].includes(value.maintenance))state.maintenance=value.maintenance;
  if(validDate(value.date))state.date=value.date;
  if(value.dailyScope==='all')state.dailyScope='all';
  if(value.periodDates&&typeof value.periodDates==='object')for(const p of periods)if(validDate(value.periodDates[p]))state.periodDates[p]=value.periodDates[p];
  if(validDay(value.customRange?.start)&&validDay(value.customRange?.end)&&value.customRange.start<=value.customRange.end)state.customRange={start:value.customRange.start,end:value.customRange.end};
  if(Number.isSafeInteger(value.page)&&value.page>0)state.page=value.page;
  if(pageSizes.includes(value.pageSize))state.pageSize=value.pageSize;
  state.advancedOpen=value.advancedOpen===true;
 }catch{/* Unavailable or outdated browser state must not prevent loading the board. */}
 return state;
}
export function boardQueryKey(state:Omit<BoardState,'page'|'advancedOpen'|'periodDates'>):string {
 return JSON.stringify([state.period,state.date,state.category,state.search,state.language,state.kind,state.tag,state.way,state.maintenance,state.dailyScope,state.customRange?.start??'',state.customRange?.end??'',state.pageSize]);
}
export function pageWindow(total:number,requested:number,pageSize:PageSize) {
 const pages=Math.max(1,Math.ceil(total/pageSize));
 const page=Math.max(1,Math.min(pages,requested));
 const start=(page-1)*pageSize;
 return {page,pages,start,end:Math.min(total,start+pageSize)};
}
export function pageNumbers(page:number,pages:number):(number|'gap')[] {
 const values=[...new Set([1,pages,...Array.from({length:5},(_,i)=>page+i-2).filter(p=>p>=1&&p<=pages)])].sort((a,b)=>a-b);
 const result:(number|'gap')[]=[];
 for(const value of values){const last=result.at(-1);if(typeof last==='number'&&value-last>1)result.push('gap');result.push(value)}
 return result;
}
