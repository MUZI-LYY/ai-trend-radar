import {useMemo} from 'react';
import {periodOptions,type SelectablePeriod} from './period-options';
import './period-selector.css';
export default function PeriodSelector({period,min,max,end,onChange}:{period:SelectablePeriod|'daily';min:string;max:string;end:string;onChange:(end:string)=>void}){
 const options=useMemo(()=>period==='daily'?[]:periodOptions(period,min,max),[period,min,max]);
 if(period==='daily')return <section className="period-selector" aria-label="选择日榜日期">
  <label htmlFor="daily-source-date">日期<input id="daily-source-date" type="date" min={min} max={max} value={end} onChange={event=>{if(event.target.value>=min&&event.target.value<=max)onChange(event.target.value)}}/></label>
  <p aria-live="polite">{end===max?'最新统计日':'按官方 Star 日历史回溯；未保存的日期不冒充当时快照'}</p>
  <button type="button" onClick={()=>onChange(max)}>最新一天</button>
 </section>;
 const selected=options.find(o=>o.start<=end&&o.end>=end)??options[0];
 if(!selected)return null;
 const years=[...new Set(options.map(o=>o.year))];
 const inYear=options.filter(o=>o.year===selected.year);
 return <section className="period-selector" aria-label="选择榜单周期">
  <label>年份<select value={selected.year} onChange={e=>onChange(options.find(o=>o.year===e.target.value)!.end)}>{years.map(year=><option key={year} value={year}>{year} 年</option>)}</select></label>
  {period!=='yearly'&&<label>{period==='monthly'?'月份':'周次'}<select value={selected.value} onChange={e=>onChange(e.target.value)}>{inYear.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}</select></label>}
  <p aria-live="polite">{selected.start} — {end<selected.end?end:selected.end}{selected.start<min?' · 起始部分暂无日数据':''}</p>
  <button type="button" onClick={()=>onChange(max)}>最新{period==='weekly'?'一周':period==='monthly'?'月份':'年份'}</button>
 </section>;
}
