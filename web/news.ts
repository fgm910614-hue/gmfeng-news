import { reviewed } from './editorial';
import reviewSignatures from './data/reviewed-signatures.json';
import localImages from './data/images.json';
export type Raw = {id:string;title:string;title_zh?:string;summary?:string;summary_zh?:string;url:string;source:string;published:string;image?:string;region?:string;topic?:string;category?:string;[key:string]:unknown};
export type Event = {id:string;title:string;summary:string;original:string;published:string;firstPublished:string;image:string;imageSource?:string;regions:string[];places:string[];regionBasis:string;topic:string;kind:string;score:number;dimensions:{label:string;value:number;max:number;reason:string}[];sources:{name:string;url:string;title:string;original:string;published:string}[];reviewed:boolean;mergedBy:string};
export const REGION_ORDER=['中国','亚洲','欧洲','美洲','中东与非洲','大洋洲','跨地区'];
export const TOPICS=['国际政治','商业经济','科技与 AI','社会民生','科学环境','文化生活'];
export function clean(s:unknown){return String(s||'').replace(/<[^>]*>/g,'').replace(/&amp;/g,'&').replace(/&#\d+;/g,'').replace(/\s+/g,' ').trim();}
export function canonical(s:string){try{const u=new URL(s);if(u.protocol!=='https:')return '';for(const k of [...u.searchParams.keys()])if(/^(utm_|at_|traffic_source|fbclid)/.test(k))u.searchParams.delete(k);u.hash='';return u.toString().replace(/\/$/,'');}catch{return '';}}
// Pinned to the reviewed source text: later updates must not inherit stale editorial copy.
function editorialFor(n:Raw){return (reviewSignatures as Record<string,string>)[n.id]===hash(clean(n.title)+'\n'+clean(n.summary))?reviewed[n.id]:undefined;}
const lower=(n:Raw)=>clean(n.title+' '+n.title_zh).toLowerCase();
const geography:{r:string;p:string;re:RegExp}[]=[
{r:'中国',p:'香港',re:/hong kong|香港|legco/i},{r:'中国',p:'台湾',re:/taiwan|taipei|台湾|台灣|台海/i},
{r:'中国',p:'中国大陆',re:/\bchina\b|\bbeijing\b|\bshenzhen\b|中国|中國|北京|深圳|解放军/i},
{r:'亚洲',p:'日本',re:/\bjapan|tokyo|日本|东京/i},{r:'亚洲',p:'韩国',re:/south korea|韩国|韓國/i},{r:'亚洲',p:'东南亚',re:/singapore|傅海燕|indonesia|malaysia|najib|simba|新加坡|印尼|马来西亚|納吉|纳吉/i},{r:'亚洲',p:'印度',re:/\bindia\b|印度/i},
{r:'欧洲',p:'欧洲',re:/\buk\b|britain|british|france|french|german|lithuania|ukraine|russia|turk|欧洲|英国|法国|立陶宛|俄罗斯|俄乌|俄军|乌克兰|土耳其/i},
{r:'美洲',p:'美国',re:/\bus\b|\bu\.s\.|united states|trump|biden|hegseth|massie|white house|american|musk|美国|特朗普|拜登|赫格塞思|马斯克/i},
{r:'美洲',p:'拉丁美洲',re:/argentina|milei|brazil|阿根廷|米莱|巴西/i},
{r:'中东与非洲',p:'中东',re:/iran|gaza|qatar|israel|egypt|abu dhabi|uae|阿布扎比|阿联酋|伊朗|加沙|卡塔尔|以色列|埃及/i},
{r:'中东与非洲',p:'非洲',re:/south africa|\banc\b|senegal|uganda|ethiopia|埃塞俄比亚|南非|非国大/i},
{r:'大洋洲',p:'澳大利亚',re:/victoria|darwin|australia|北领地|维州|维多利亚|达尔文|澳大利亚/i},{r:'大洋洲',p:'新西兰',re:/new zealand|新西兰/i}
];
export function locate(n:Raw){const t=lower(n);const hits=geography.filter(x=>x.re.test(t));if(hits.length)return {regions:[...new Set(hits.map(x=>x.r))],places:[...new Set(hits.map(x=>x.p))],basis:'依据标题中的事件地点与参与方；可同时归属多个地区'};
// A publisher's location is never evidence of an event's location.
return {regions:['跨地区'],places:['地点待确认'],basis:'标题无明确地点，保留为跨地区；未根据媒体所在地推断'};}
export function topic(n:Raw){const t=lower(n);if(/climate|net zero|emission|cop31|气候|排放|电动车销售/.test(t))return '科学环境';if(/booker|novel|lewis|infertility|布克|小说|刘易斯|不孕/.test(t))return '文化生活';if(/ai\b|nvidia|gpu|spy tools|cyber|科技|人工智能|英伟达|网络攻击|频谱|窃听/.test(t))return '科技与 AI';if(/airline|air india|austerity|econom|航空|紧缩|经济/.test(t))return '商业经济';if(/hospital|pain|flood|blast|explosion|shot|student aid|cruise|医院|疼痛|洪|爆炸|枪击|辅助会|邮轮/.test(t))return '社会民生';return '国际政治';}
export function normalizeNames(text:string) {
  return text.replace(/Jensen\s+Huang|Jen-Hsun\s+Huang|黃仁勳/gi,'黄仁勋')
    .replace(/NVIDIA|輝達|辉达|英偉達/gi,'英伟达');
}
export function polishTitle(n:Raw){let zh=clean(n.title_zh);const broken=/[,，:：]$/.test(zh)||zh.length<8;const sentence=clean(n.summary_zh).split(/[。！？]/)[0];if(broken&&sentence.length>=12&&sentence.length<=65)zh=sentence;else if(broken)zh=n.title;return normalizeNames(clean(zh||n.title)).replace(/黄詹森|黄延生/g,'黄仁勋').replace(/恩维迪亚/g,'英伟达').replace(/\s*([，。！？：；])\s*/g,'$1').replace(/[,，。；;]+$/,'');}
const eventRules:[string,RegExp][]=[
 ['turkey-steel-blast',/((turk|土耳其).*(steel|钢|鋼).*(blast|explosion|爆炸))|((explosion|blast).*turk)/i],
 ['gaza-floods',/(gaza|加沙).*(flood|洪水|暴雨)|(flood|洪水).*(gaza|加沙)/i],
 ['iran-war-over',/(iran|伊朗).*(effectively over|基本结束|有效结束)|(effectively over|基本结束|有效结束).*(iran|伊朗)/i],
 ['hegseth-impeach',/(hegseth|赫格塞思|赫格塞斯).*(impeach|弹劾)|(impeach|弹劾).*(hegseth|赫格塞思|赫格塞斯)/i],
 ['huang-resignation', /(?=.*(?:nvidia|英伟达|輝達))(?=.*(?:jensen huang|黄仁勋|黃仁勳))(?=.*(?:resigned|resigns|辞任|辭任))/i],
 ['huang-allegations',/(nvidia|huang|黄仁勋|黃仁勳|英伟达|輝達).*(affair|spy|scandal|allegations|风波|间谍|私情|争议|丑闻|指控|風波|間諜|外遇)|(affair|spy|scandal).*(nvidia|huang)/i]
];
function groupKey(n:Raw){const t=lower(n); // Keep policy effects and distinct opinion angles as separate events.
if(/commentary|opinion|分析：|评论：|may test|gpu|supplies/.test(t))return '';
return eventRules.find(([,r])=>r.test(t))?.[0]||'';}
const stop=new Set('the a an in on at of for as to is are has have and with over after says said what why how from its it will by not this that live video'.split(' '));
function tokens(s:string){return new Set(clean(s).toLowerCase().replace(/[^a-z0-9\s]/g,' ').split(/\s+/).filter(t=>t.length>2&&!stop.has(t)));}
function similar(a:Raw,b:Raw){const x=tokens(a.title),y=tokens(b.title);const overlap=[...x].filter(t=>y.has(t)); // Require uncommon entities plus near-identical action words, not shared topic alone.
return x.size>=5&&y.size>=5&&overlap.length>=5&&overlap.length/(x.size+y.size-overlap.length)>=.64;}
function hash(s:string){let x=2166136261;for(const c of s)x=Math.imul(x^c.charCodeAt(0),16777619);return (x>>>0).toString(36);}
export function buildEvents(input:Raw[]):Event[]{const groups:{key:string;rows:Raw[];method:string}[]=[];const urls=new Set<string>();for(const row of input){if(!row||!clean(row.title)||!canonical(row.url)||!Number.isFinite(Date.parse(row.published)))continue;const n={...row,title:clean(row.title),title_zh:editorialFor(row)?.[0]||row.title_zh,url:canonical(row.url)};if(urls.has(n.url))continue;urls.add(n.url);const key=groupKey(n);const found=groups.find(g=>Math.abs(Date.parse(g.rows[0].published)-Date.parse(n.published))<=72*3600000&&((key&&g.key===key)||g.rows.some(r=>clean(r.title).toLowerCase()===n.title.toLowerCase()||similar(r,n))));if(found){found.rows.push(n);found.method=key?'共同实体与事件动作（72小时内）':'标题实体与动作高度相似（72小时内）';}else groups.push({key,rows:[n],method:'单篇报道'});}
return groups.map(g=>{g.rows.sort((a,b)=>Date.parse(b.published)-Date.parse(a.published));const primary=g.rows[0];const edit=editorialFor(primary);const locs=g.rows.map(locate);const regions=[...new Set(locs.flatMap(x=>x.regions))].filter(x=>x!=='跨地区');const t=g.rows.map(lower).join(' ');const cat=topic(primary);const transition = /(?:resigns?|resigned|steps down|辞任|辭任)/i.test(t) && /(?:CEO|chief executive|首席执行官|執行長)/i.test(t);const publicImpact=transition?3.7:/war|战争|会谈|talks|爆炸|blast|explosion|flood|洪水|暴雨|impeach|弹劾|election|选举/.test(t)?3.7:/policy|政府|议员|hospital|医院|climate|气候|funding|拨款/.test(t)?3.1:2.3;const breadth=regions.length>1?2.6:/national|全国|总统|president|war|战争|climate|气候|nvidia|英伟达/.test(t)?2.1:1.4;const lasting=transition?1.9:/war|战争|会谈|talks|policy|政策|climate|气候|election|选举|hospital|医院|education|教育|ai\b|人工智能|议案|频谱/.test(t)?1.8:1.1;const media=new Set(g.rows.map(n=>n.source.startsWith('BBC')?'BBC':n.source.startsWith('Guardian')?'Guardian':n.source.startsWith('SCMP')?'SCMP':n.source.startsWith('CNA')?'CNA':n.source.startsWith('ABC')?'ABC':n.source.replace(/ (English|All)$/, ''))).size;const cross=media>1?.8:.3;const dimensions=[{label:'公共影响',value:publicImpact,max:4,reason:'生命安全、公共政策及公共服务的影响程度'},{label:'影响范围',value:breadth,max:3,reason:'标题涉及的地区与受影响群体；不按媒体所在地判断'},{label:'持续影响',value:lasting,max:2,reason:'政策、冲突、气候与技术等长期影响线索'},{label:'报道广度',value:cross,max:1,reason:`${media} 家媒体的报道；不代表独立证实`}];
const photos = g.rows.map(row => ({
  url: (localImages as Record<string,string>)[row.id] || row.image,
  source: row.source
}));
const photo = photos.find(candidate => candidate.url?.startsWith('/images/')) || photos.find(candidate => candidate.url);
const title=edit?.[0]||polishTitle(primary);const summary=edit?.[1]||clean(primary.summary_zh||primary.summary);
return {id:hash((g.key||canonical(primary.url))+'|'+(g.key?g.rows.at(-1)!.published.slice(0,10):'')),title,summary,original:primary.title,published:primary.published,firstPublished:g.rows.at(-1)!.published,image:photo?.url||'',imageSource:photo?.source,regions:regions.length?regions:['跨地区'],places:[...new Set(locs.flatMap(x=>x.places))],regionBasis:locs[0].basis,topic:cat,kind:/commentary|opinion|评论|观点/.test(t)?'观点':/analysis|explains|解读|分析/.test(t)?'解读':'报道',score:Math.round(dimensions.reduce((a,x)=>a+x.value,0)*10)/10,dimensions,sources:g.rows.map(n=>({name:n.source,url:n.url,title:editorialFor(n)?.[0]||clean(n.title_zh||n.title),original:n.title,published:n.published})),reviewed:!!edit,mergedBy:g.method};}).sort((a,b)=>b.score-a.score||Date.parse(b.published)-Date.parse(a.published));}
