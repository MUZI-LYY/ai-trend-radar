import {weekStart} from './ranking';
export default function ArchiveBrowser({dates,value,onChange}:{dates:{date:string;file:string}[];value:string;onChange:(date:string)=>void}){
 const available=dates.map(d=>d.date).sort().reverse();const chosen=value==='latest'?available[0]:value;
 if(!chosen)return null;
 const year=chosen.slice(0,4),month=chosen.slice(0,7),week=weekStart(chosen);
 const unique=(values:string[])=>[...new Set(values)];
 const years=unique(available.map(d=>d.slice(0,4))),months=unique(available.filter(d=>d.startsWith(year)).map(d=>d.slice(0,7)));
 const weeks=unique(available.filter(d=>d.startsWith(month)).map(weekStart)),days=available.filter(d=>d.startsWith(month)&&weekStart(d)===week);
 function select(match:(date:string)=>boolean){const date=available.find(match);if(date)onChange(date)}
 return <details className="archive-browser"><summary>历史榜单 · 按年 / 月 / 周 / 日查找</summary><div className="archive-fields">
 <label>年<select aria-label="归档年份" value={year} onChange={e=>select(d=>d.startsWith(e.target.value))}>{years.map(y=><option key={y} value={y}>{y} 年</option>)}</select></label>
 <label>月<select aria-label="归档月份" value={month} onChange={e=>select(d=>d.startsWith(e.target.value))}>{months.map(m=><option key={m} value={m}>{Number(m.slice(5))} 月</option>)}</select></label>
 <label>周<select aria-label="归档周" value={week} onChange={e=>select(d=>d.startsWith(month)&&weekStart(d)===e.target.value)}>{weeks.map(w=><option key={w} value={w}>{w.slice(5)} 起的一周</option>)}</select></label>
 <label>日<select aria-label="归档日期" value={chosen} onChange={e=>onChange(e.target.value)}>{days.map(d=><option key={d} value={d}>{Number(d.slice(8))} 日</option>)}</select></label>
 <button onClick={()=>onChange(chosen)}>查看此日归档</button><button onClick={()=>onChange('latest')}>返回最新</button>
 </div><p>按实际归档日期分组，只列出已有快照；榜单统计截止日单独展示。跨月周可在对应月份查看。</p></details>
}
