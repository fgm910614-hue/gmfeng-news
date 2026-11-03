"""GMFENG NEWS transparent editorial heuristics; no paid AI or external calls.
Scores represent editorial prioritization, NOT truthfulness or reliability ratings.
"""
import re
import math
import difflib
import unicodedata
from collections import Counter
from urllib.parse import urlsplit, parse_qsl, urlencode, urlunsplit

REGIONS = ('中国','亚洲','欧洲','美洲','中东非洲','大洋洲')
# Title-based event location first. Sources provide a fallback only.
PLACES = {
 '中国': r'(?<![a-z])(?:china|chinese|hong kong|taiwan|macau|beijing|shanghai|shenzhen)(?![a-z])|中国|香港|台湾|澳门|北京|上海|深圳|广州',
 '亚洲': r'(?<![a-z])(?:japan|japanese|south korea|north korea|korean|india|indian|singapore|thailand|thai|vietnam|indonesia|malaysia|philippines|pakistan|bangladesh|myanmar|nepal|asia|asean)(?![a-z])|日本|韩国|朝鲜|印度|新加坡|泰国|越南|印尼|马来西亚|菲律宾|巴基斯坦|孟加拉|缅甸|亚洲|东盟',
 '欧洲': r'(?<![a-z])(?:europe|european union|eu leaders|britain|british|uk|england|france|french|germany|german|italy|italian|spain|spanish|ukraine|ukrainian|russia|russian|poland|turkey|turkish)(?![a-z])|欧洲|欧盟|英国|法国|德国|意大利|西班牙|乌克兰|俄罗斯|波兰|土耳其',
 '美洲': r'(?<![a-z])(?:united states|u\.s\.|usa|american|america|white house|washington|canada|canadian|mexico|mexican|brazil|brazilian|argentina|argentine|latin america|colombia|chile|peru)(?![a-z])|美国|白宫|加拿大|墨西哥|巴西|阿根廷|拉美|哥伦比亚|智利|秘鲁',
 '中东非洲': r'(?<![a-z])(?:middle east|africa|african|israel|israeli|gaza|palestin|iran|iranian|saudi|syria|syrian|lebanon|iraq|yemen|egypt|egyptian|nigeria|kenya|south africa|sudan)(?![a-z])|中东|非洲|以色列|加沙|巴勒斯坦|伊朗|沙特|叙利亚|黎巴嫩|伊拉克|也门|埃及|尼日利亚|肯尼亚|南非|苏丹',
 '大洋洲': r'(?<![a-z])(?:australia|australian|new zealand|zealand|oceania|fiji|papua new guinea)(?![a-z])|澳大利亚|新西兰|大洋洲|斐济|巴布亚新几内亚',
}
COMPILED = {k: re.compile(v,re.I) for k,v in PLACES.items()}
TOPIC_PATTERNS = [
 ('政治',r'(?<![a-z])(?:election|vote|parliament|president|prime minister|minister|government|policy|congress|senate|protest|diplomacy|summit)(?![a-z])|选举|议会|总统|总理|政府|外交|政策|抗议|峰会'),
 ('商业',r'(?<![a-z])(?:economy|economic|inflation|interest rate|central bank|stocks|markets|trade|tariff|business|profit|earnings|gdp)(?![a-z])|经济|通胀|央行|利率|贸易|关税|股市|利润|财报|市场'),
 ('科技',r'(?<![a-z])(?:artificial intelligence|ai|semiconductor|chipmaker|chips|robot|cybersecurity|technology|software)(?![a-z])|人工智能|芯片|半导体|机器人|网络安全|科技'),
 ('科学',r'(?<![a-z])(?:research|scientists|science|spacecraft|climate|environment|vaccine)(?![a-z])|科学|研究|航天|气候|环境|疫苗'),
 ('安全',r'(?<![a-z])(?:war|ceasefire|airstrike|attack|invasion|conflict|military|earthquake|flood|typhoon|hurricane)(?![a-z])|战争|停火|空袭|袭击|冲突|地震|洪水|台风|飓风'),
]
TOPIC_COMPILED = [(k,re.compile(v,re.I)) for k,v in TOPIC_PATTERNS]
STOP = {'the','a','an','of','to','in','on','for','and','or','at','as','by','with','from','after','over','amid','into','is','are','was','were','will','could','would','may','new','latest','live','update','breaking','says','say','said','about','how','why','what','who','this','that','its','their','his','her','first','more','than','under','up','down','world','news','global','today'}

def normalize_url(url):
 try:
  p=urlsplit(url or '')
  if p.scheme not in ('https','http'):return ''
  qs=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid','mc_cid','mc_eid')]
  return urlunsplit((p.scheme.lower(),p.netloc.lower().removeprefix('www.'),p.path.rstrip('/') or '/',urlencode(qs),''))
 except ValueError:return ''

def tokens(title):
 s=unicodedata.normalize('NFKC',str(title or '')).lower()
 s=re.sub(r'\b(?:breaking|live updates?|exclusive|latest)\b',' ',s)
 return {w for w in re.findall(r'[a-z][a-z0-9]{2,}|\d+(?:\.\d+)?|[\u4e00-\u9fff]{2,}',s) if w not in STOP}

def region_for(item):
 title=str(item.get('title') or '')
 hits={r:len(p.findall(title)) for r,p in COMPILED.items()}
 if any(hits.values()):
  region=max(REGIONS,key=lambda r:hits[r])
  return region,'标题地点关键词（启发式）'
 category=str(item.get('category') or '')
 if category in REGIONS:return category,'来源栏目推断（低置信度）'
 return '其他','地区未确定'

def topic_for(item):
 text=str(item.get('title') or '')+' '+str(item.get('summary') or '')[:180]
 hits=[(topic,len(pattern.findall(text))) for topic,pattern in TOPIC_COMPILED]
 if max((n for _,n in hits),default=0):return max(hits,key=lambda x:x[1])[0]
 category=str(item.get('category') or '')
 if category=='商业经济':return '商业'
 if category=='科技AI':return '科技'
 if category=='科学环境':return '科学'
 return '综合'

def editorial_score(item,now=None):
 """Conservative 0-10 editorial priority score, with explainable reasons."""
 title=str(item.get('title') or '')
 summary=str(item.get('summary') or '')
 content=(title+' '+summary[:300]).lower()
 score=5.0;reasons=[]
 major=[(r'(?<![a-z])(?:ceasefire|invasion|earthquake|hurricane|emergency|election results|central bank|interest rate decision|gdp|major breakthrough)(?![a-z])|停火|地震|飓风|紧急状态|选举结果|央行|利率决议|重大突破',1.6,'重大公共事件'),
 (r'(?<![a-z])(?:election|parliament|president|prime minister|government|summit|war|conflict|tariff|inflation|ai|semiconductor)(?![a-z])|选举|议会|总统|总理|政府|战争|冲突|关税|通胀|人工智能|芯片',0.9,'公共政策或产业影响'),
 (r'(?<![a-z])(?:climate|flood|public health|science|research|energy|trade)(?![a-z])|气候|洪水|公共卫生|科学|研究|能源|贸易',0.5,'公共利益相关')]
 for pat,weight,reason in major:
  if re.search(pat,content,re.I):score+=weight;reasons.append(reason)
 if len(title)<14:score-=0.3
 if not summary:score-=0.3
 if re.search(r'(?i)\b(?:opinion|editorial|review|horoscope|celebrity gossip|live blog)\b|星座|娱乐八卦|评论文章',title):score-=1.1;reasons.append('观点或轻资讯降权')
 # Avoid equating a publisher, geography, or repeated keywords with importance.
 score=max(0,min(9.5,round(score,1)))
 return score,('；'.join(reasons) if reasons else '常规新闻')+'；规则优先级估计，非事实可信度评级'

def duplicate_reason(a,b):
 """Return reason only for high-confidence same-event pairs; prefer false negatives to false merges."""
 u,v=normalize_url(a.get('url')),normalize_url(b.get('url'))
 if u and u==v:return 'same_url'
 ta,tb=str(a.get('title') or ''),str(b.get('title') or '')
 if not ta or not tb:return None
 na=re.sub(r'[^\w]+','',unicodedata.normalize('NFKC',ta).lower())
 nb=re.sub(r'[^\w]+','',unicodedata.normalize('NFKC',tb).lower())
 if na==nb:return 'same_title'
 A,B=tokens(ta),tokens(tb)
 if not A or not B:return None
 shared=A&B
 if len(shared)<3:return None
 jac=len(shared)/len(A|B)
 cover=len(shared)/min(len(A),len(B))
 if jac>=0.74 and cover>=0.82:return 'same_event_tokens'
 if jac>=0.54 and cover>=0.78 and difflib.SequenceMatcher(None,na,nb).ratio()>=0.73:return 'same_event_similarity'
 return None

def deduplicate(items):
 kept=[];stats=Counter()
 for item in items:
  reason=next((r for old in kept if (r:=duplicate_reason(item,old))),None)
  if reason:stats[reason]+=1
  else:kept.append(item)
 return kept,dict(stats)

# Exact substitutions only; avoid generative rewrites that might alter facts.
ZH_TITLE_TERMS = [
 (r'训斥辩论','不信任辩论'),
 (r'不信任投票辩论','不信任案辩论'),
 (r'人工智能智能','人工智能'),
 (r'美利坚合众国总统','美国总统'),
 (r'联合国组织','联合国'),
]
def polish_zh_title(title):
 s=re.sub(r'\s+',' ',str(title or '')).strip()
 for old,new in ZH_TITLE_TERMS:s=re.sub(old,new,s)
 s=re.sub(r'\s+([，。！？：；])',r'\1',s)
 s=re.sub(r'([，。！？：；])\1+',r'\1',s)
 return s
