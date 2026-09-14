import {useMemo} from 'react';
import {periodOptions,type SelectablePeriod} from './period-options';
import './period-selector.css';
export default function PeriodSelector({period,min,max,end,onChange}:{period:SelectablePeriod;min:string;max:string;end:string;onChange:(end:string)=>void}){
 const options=useMemo(()=>periodOptions(period,min,max),[period,min,max]);
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
