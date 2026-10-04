/** Read a checked history artifact whether the host preserves or decodes gzip. */
export async function parseHistoryResponse<T>(response: Response): Promise<T> {
 const bytes=await response.arrayBuffer();
 const prefix=new Uint8Array(bytes,0,Math.min(bytes.byteLength,2));
 if(prefix[0]===0x1f&&prefix[1]===0x8b){
  if(typeof DecompressionStream==='undefined')throw Error('当前浏览器无法读取压缩历史数据。');
  return new Response(new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'))).json() as Promise<T>;
 }
 return JSON.parse(new TextDecoder().decode(bytes)) as T;
}
