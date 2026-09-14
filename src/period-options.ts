import {weekStart} from './ranking';
export type SelectablePeriod='weekly'|'monthly'|'yearly';
export interface PeriodOption {year:string;value:string;start:string;end:string;label:string}
const dayMs=86400000;
const shift=(day:string,n:number)=>new Date(Date.parse(day+'T00:00:00Z')+n*dayMs).toISOString().slice(0,10);
export function periodOptions(period:SelectablePeriod,min:string,max:string):PeriodOption[]{
 const rows:PeriodOption[]=[];
 let start=period==='weekly'?weekStart(min):min.slice(0,period==='monthly'?7:4)+(period==='monthly'?'-01':'-01-01');
 while(start<=max){
  let next:string,year=start.slice(0,4),label:string;
  if(period==='weekly'){
   next=shift(start,7);year=shift(start,3).slice(0,4);
   const first=weekStart(year+'-01-04');
   const week=Math.round((Date.parse(start)-Date.parse(first))/(7*dayMs))+1;
   label=`第 ${week} 周 · ${start.slice(5)} — ${shift(next,-1).slice(5)}`;
  }else{
   const date=new Date(start+'T00:00:00Z');
   if(period==='monthly')date.setUTCMonth(date.getUTCMonth()+1);else date.setUTCFullYear(date.getUTCFullYear()+1);
   next=date.toISOString().slice(0,10);label=period==='monthly'?`${Number(start.slice(5,7))} 月`:`${year} 年`;
  }
  const naturalEnd=shift(next,-1),end=naturalEnd>max?max:naturalEnd;
  rows.push({year,value:end,start,end,label:label+(naturalEnd>max?' · 未结束':'')});start=next;
 }
 return rows.reverse();
}
