import {useId,useState} from 'react';

export interface TimeRange {start:string;end:string}

export default function CustomTimeRange({min,max,value,onApply}:{min:string;max:string;value:TimeRange|null;onApply:(range:TimeRange)=>void}){
 const id=useId();
 const [start,setStart]=useState(value?.start??[min,max.slice(0,4)+'-01-01'].sort().at(-1)!);
 const [end,setEnd]=useState(value?.end??max);
 const [error,setError]=useState('');
 return <form className="custom-time-range" onSubmit={event=>{
  event.preventDefault();
  const values=new FormData(event.currentTarget);
  const startValue=values.get('start'),endValue=values.get('end');
  const start=typeof startValue==='string'?startValue:'',end=typeof endValue==='string'?endValue:'';
  if(!start||!end||start>end||start<min||end>max){setError('请选择可用范围内的日期，开始日期不能晚于结束日期。');return}
  setError('');onApply({start,end});
 }}>
  <div className="range-fields">
   <label htmlFor={id+'-start'}>开始日期<input id={id+'-start'} type="date" name="start" required min={min} max={max} value={start} aria-invalid={!!error} aria-describedby={id+'-hint'} onChange={e=>{setStart(e.target.value);setError('')}}/></label>
   <span className="range-separator" aria-hidden="true">—</span>
   <label htmlFor={id+'-end'}>结束日期<input id={id+'-end'} type="date" name="end" required min={min} max={max} value={end} aria-invalid={!!error} aria-describedby={id+'-hint'} onChange={e=>{setEnd(e.target.value);setError('')}}/></label>
   <button type="submit">查看榜单</button>
  </div>
  <p id={id+'-hint'} role={error?'alert':undefined}>{error||'汇总起止日期（含当天）内每天日榜 TOP 30，项目去重，只累加上榜日新增 Star。'}</p>
 </form>
}
