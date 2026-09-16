import {pageNumbers,pageSizes,type PageSize} from './board-state';
import './pagination.css';
export default function Pagination({page,pages,total,start,end,pageSize,onPage,onPageSize}:{page:number;pages:number;total:number;start:number;end:number;pageSize:PageSize;onPage:(page:number)=>void;onPageSize:(size:PageSize)=>void}) {
 return <nav className="pagination" aria-label="榜单分页">
  <div className="pagination-summary"><span role="status">共 {total} 项 · 第 {total?start+1:0}–{end} 项 · 第 {page}/{pages} 页</span><label>每页<select aria-label="每页条数" value={pageSize} onChange={event=>onPageSize(Number(event.target.value) as PageSize)}>{pageSizes.map(size=><option key={size} value={size}>{size} 条</option>)}</select></label></div>
  <div className="pagination-pages"><button type="button" disabled={page===1} onClick={()=>onPage(page-1)}>上一页</button>{pageNumbers(page,pages).map((number,index)=>number==='gap'?<span className="pagination-gap" key={`gap-${index}`} aria-hidden="true">…</span>:<button type="button" key={number} aria-label={`第 ${number} 页`} aria-current={number===page?'page':undefined} onClick={()=>onPage(number)}>{number}</button>)}<button type="button" disabled={page===pages} onClick={()=>onPage(page+1)}>下一页</button></div>
 </nav>;
}
