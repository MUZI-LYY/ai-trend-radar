import {useEffect,useLayoutEffect,useRef} from 'react';
const positionKey='ai-radar:board-position:v1';
const isBoard=(hash:string)=>!hash.startsWith('#/project/')&&hash!=='#/about';
type Position={key:string;y:number;href:string|null};
function readPosition():Position|null {
 try{const value=JSON.parse(sessionStorage.getItem(positionKey)??'null');return value&&typeof value.key==='string'&&Number.isFinite(value.y)&&value.y>=0?{key:value.key,y:value.y,href:typeof value.href==='string'?value.href:null}:null}catch{return null}
}
export function useBoardNavigation(hash:string,setHash:(value:string)=>void,ready:boolean,viewKey:string) {
 const position=useRef<Position|null>(readPosition());
 const key=useRef(viewKey),canSave=useRef(false),pending=useRef(true),pageScroll=useRef(false),previousHash=useRef(hash);
 const persist=()=>{try{sessionStorage.setItem(positionKey,JSON.stringify(position.current))}catch{/* Private browser modes may disable storage. */}};
 useLayoutEffect(()=>{key.current=viewKey;canSave.current=ready&&isBoard(hash)},[viewKey,ready,hash]);
 useEffect(()=>{
  const previousRestoration=history.scrollRestoration;history.scrollRestoration='manual';
  const saveScroll=()=>{if(canSave.current&&!pending.current&&isBoard(window.location.hash))position.current={key:key.current,y:window.scrollY,href:position.current?.href??null}};
  const capture=(event:MouseEvent)=>{
   if(event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey||!isBoard(window.location.hash))return;
   const anchor=(event.target as Element).closest?.('a');const href=anchor?.getAttribute('href');
   if(href?.startsWith('#/')&&href!=='#/'){position.current={key:key.current,y:window.scrollY,href};persist()}
  };
  const navigate=()=>{if(isBoard(previousHash.current))persist();pending.current=true;pageScroll.current=false;previousHash.current=window.location.hash;setHash(window.location.hash)};
  const hide=()=>{saveScroll();persist()};
  window.addEventListener('scroll',saveScroll,{passive:true});document.addEventListener('click',capture,true);
  window.addEventListener('hashchange',navigate);window.addEventListener('pagehide',hide);
  return()=>{history.scrollRestoration=previousRestoration;window.removeEventListener('scroll',saveScroll);document.removeEventListener('click',capture,true);window.removeEventListener('hashchange',navigate);window.removeEventListener('pagehide',hide)};
 },[setHash]);
 useLayoutEffect(()=>{
  if(!ready)return;
  if(pending.current){
   if(isBoard(hash)){
    const saved=position.current?.key===viewKey?position.current:null;
    if(saved?.href)Array.from(document.querySelectorAll<HTMLAnchorElement>('a[href]')).find(a=>a.getAttribute('href')===saved.href)?.focus({preventScroll:true});
    window.scrollTo({top:saved?.y??0,behavior:'instant'});
   }else{
    window.scrollTo({top:0,behavior:'instant'});
    const title=document.querySelector<HTMLElement>('.detail-layout h1,.methodology h1');
    if(title){title.tabIndex=-1;title.focus({preventScroll:true})}
   }
   pending.current=false;
  }else if(pageScroll.current&&isBoard(hash)){
   const heading=document.getElementById('ranking-heading');heading?.focus({preventScroll:true});heading?.scrollIntoView({block:'start',behavior:'instant'});pageScroll.current=false;
  }
 },[hash,ready,viewKey]);
 return {
  scrollToResults:()=>{pageScroll.current=true},
  resetPosition:()=>{position.current=null;pending.current=true;persist()},
 };
}
