const allowed=new Set(['i.dawn.com','cdn.arstechnica.net','s.france24.com','ichef.bbci.co.uk','i.guim.co.uk','cdn.i-scmp.com','dam.mediacorp.sg','npr.brightspotcdn.com','onecms-res.cloudinary.com','live-production.wcms.abc-cdn.net.au','www.aljazeera.com','www.abc.net.au']);
export async function onRequestGet(context){
  let source;
  try{source=new URL(new URL(context.request.url).searchParams.get('url')||'');}catch{return new Response(null,{status:400});}
  if(source.protocol!=='https:'||!allowed.has(source.hostname)||source.username||source.password||source.port)return new Response(null,{status:400});
  // If a publisher cannot be fetched by the server, the browser can still load
  // the original public image. This fallback is limited to the same allowlist.
  const direct=reason=>new Response(null,{status:302,headers:{Location:source.toString(),'Cache-Control':'no-store','X-GMFENG-Image-Mode':'direct-'+reason}});
  const cache=globalThis.caches?.default,key=new Request(context.request.url);
  try{const stored=await cache?.match(key);if(stored)return stored;}catch{/* Cache availability must not break images. */}
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),8000);
  try{
    const upstream=await fetch(source.toString(),{redirect:'error',signal:controller.signal,headers:{Accept:'image/avif,image/webp,image/*'}});
    if(!upstream.ok)return direct('upstream');
    const type=upstream.headers.get('content-type')||'';
    if(!/^image\/(jpeg|png|webp|avif|gif)/.test(type))return new Response(null,{status:404});
    if(+(upstream.headers.get('content-length')||0)>5_000_000)return new Response(null,{status:413});
    const bytes=await upstream.arrayBuffer();if(bytes.byteLength>5_000_000)return new Response(null,{status:413});
    const response=new Response(bytes,{headers:{'Content-Type':type,'Cache-Control':'public, max-age=86400','X-Content-Type-Options':'nosniff','X-GMFENG-Image-Mode':'cached-proxy'}});
    if(cache)try{context.waitUntil(cache.put(key,response.clone()).catch(()=>{}));}catch{/* Return a valid image even when cache writes are unavailable. */}
    return response;
  }catch{return direct('fetch');}finally{clearTimeout(timer);}
}
