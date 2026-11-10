import { build } from 'esbuild';
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
await fs.mkdir('.sites-runtime',{recursive:true});
await build({entryPoints:['web/news.ts'],bundle:true,platform:'node',format:'esm',outfile:'.sites-runtime/news-test.mjs',logLevel:'silent'});
const {buildEvents,locate,canonical,polishTitle}=await import('../.sites-runtime/news-test.mjs?'+Date.now());
const raw=JSON.parse(await fs.readFile('site/data/news.json','utf8')).items;
const events=buildEvents(raw);
assert.ok(events.length>0&&events.length<=raw.length);
assert.equal(new Set(events.map(n=>n.id)).size,events.length);
const unique=new Set(raw.filter(n=>n.title&&canonical(n.url)&&Number.isFinite(Date.parse(n.published))).map(n=>canonical(n.url)));
assert.equal(events.flatMap(n=>n.sources).length,unique.size,'Every valid unique source report must remain accessible');
assert.deepEqual(locate({title:'A new art exhibition opens',title_zh:'一场艺术展览开幕',source:'SCMP China'}).regions,['跨地区']);
assert.equal(canonical('javascript:alert(1)'), '');
assert.equal(canonical('https://a.example/news?utm_source=x&at_campaign=rss'),'https://a.example/news');
assert.equal(polishTitle({title:'Original complete headline',title_zh:'由于洪水，',summary_zh:'加沙数万顶帐篷被暴雨淹没。当地救援承压。'}),'加沙数万顶帐篷被暴雨淹没');
const updated=buildEvents([{id:'dbedcaa7a86dba96a23c',title:'Turkey steel factory blast kills at least 18 people',title_zh:'土耳其钢厂爆炸造成至少18人死亡',summary:'Updated report',url:'https://example.com/updated',source:'BBC World',published:'2026-11-10T10:00:00Z'}])[0];
assert.ok(updated.title.includes('18'),'Updated reports must not inherit an older reviewed headline');assert.equal(updated.reviewed,false);
const sample=(title,url,published='2026-11-10T00:00:00Z')=>({id:url,title,url,source:'Test',published});
assert.equal(buildEvents([sample('Turkey steel factory blast kills at least 17 people','https://a.example/1'),sample('Explosion at Turkish steel plant kills at least 16 people','https://b.example/2')]).length,1);
assert.equal(buildEvents([sample('Turkey steel factory blast kills at least 17 people','https://a.example/1'),sample('Turkey steel factory blast kills at least 17 people','https://b.example/2','2026-12-10T00:00:00Z')]).length,2);
assert.ok(!locate({title:'Ethiopian Airlines and Air India',title_zh:'埃塞俄比亚航空与印度航空'}).regions.includes('欧洲'));
for(const n of events){assert.ok(n.score>=0&&n.score<=10);assert.equal(Math.round(n.dimensions.reduce((s,d)=>s+d.value,0)*10)/10,n.score);}
const html=await fs.readFile('site/index.html','utf8');
for(const path of [...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g)].map(x=>'site'+x[1]))assert.ok((await fs.stat(path)).size>0);
const ui=await fs.readFile('web/reader.tsx','utf8');
assert.ok(ui.includes("fetch('/data/news.json"));assert.ok(!ui.includes('私有版'));assert.ok(!ui.includes('仅限所有者访问'));
// Pages image boundary: only configured HTTPS publisher hosts may be fetched.
const {onRequestGet}=await import('../functions/api/image.js');const oldFetch=globalThis.fetch,oldCaches=globalThis.caches;let called=0;
try{globalThis.fetch=async()=>{called++;return new Response(new Uint8Array([255,216,255]),{headers:{'Content-Type':'image/jpeg'}})};
const get=url=>onRequestGet({request:new Request('https://news.gmfeng.com/api/image?url='+encodeURIComponent(url)),waitUntil:()=>{}});
assert.equal((await get('https://example.com/photo.jpg')).status,400);assert.equal(called,0);
assert.equal((await get('https://s.france24.com/photo.jpg')).status,200);
globalThis.caches={default:{match:async()=>undefined,put:async()=>{}}};const context={request:new Request('https://news.gmfeng.com/api/image?url=https%3A%2F%2Fs.france24.com%2Fphoto.jpg'),waitUntil(promise){assert.equal(this,context);}};assert.equal((await onRequestGet(context)).status,200);globalThis.caches=oldCaches;
globalThis.fetch=async()=>new Response('<html>not an image</html>',{headers:{'Content-Type':'text/html'}});assert.equal((await get('https://s.france24.com/photo.jpg')).status,404);
globalThis.fetch=async()=>{throw new Error('Upstream unavailable')};const fallback=await get('https://s.france24.com/photo.jpg');assert.equal(fallback.status,302);assert.equal(fallback.headers.get('Location'),'https://s.france24.com/photo.jpg');
}finally{globalThis.fetch=oldFetch;globalThis.caches=oldCaches;}
console.log(`PASS: ${raw.length} reports → ${events.length} events; all source links retained; geography, score, title fallback, deployment assets and image boundary verified.`);
