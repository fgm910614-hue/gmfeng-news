#!/usr/bin/env python3
"""Daily Signal: dependency-free RSS news site with SQLite history."""
import os, json, sqlite3, urllib.request, urllib.parse, xml.etree.ElementTree as ET, re, html, hashlib, datetime, threading, time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from email.utils import parsedate_to_datetime
ROOT=Path(__file__).resolve().parent
DB=Path(os.environ.get('NEWS_DB',str(ROOT/'news.db')))
PORT=int(os.environ.get('PORT','8080'))
FEEDS=[
 ('BBC World','全球','https://feeds.bbci.co.uk/news/world/rss.xml'),
 ('BBC Business','商业经济','https://feeds.bbci.co.uk/news/business/rss.xml'),
 ('BBC Technology','科技AI','https://feeds.bbci.co.uk/news/technology/rss.xml'),
 ('BBC Science','科学环境','https://feeds.bbci.co.uk/news/science_and_environment/rss.xml'),
 ('Guardian World','全球','https://www.theguardian.com/world/rss'),
 ('Guardian Technology','科技AI','https://www.theguardian.com/uk/technology/rss'),
 ('DW China','中国','https://rss.dw.com/rdf/rss-chi-all'),
 ('UN News Chinese','全球','https://news.un.org/feed/subscribe/zh/news/all/rss.xml'),
 ('BBC Chinese','中国','https://feeds.bbci.co.uk/zhongwen/simp/rss.xml'),
 ('UN News','全球','https://news.un.org/feed/subscribe/en/news/all/rss.xml'),
 ('NPR World','全球','https://feeds.npr.org/1004/rss.xml'),
 ('NPR Business','商业经济','https://feeds.npr.org/1006/rss.xml'),
 # 地域定向来源：优先使用媒体直接发布的 RSS，避免 Google News 聚合 RSS 的 503。
 ('BBC Asia','亚洲','https://feeds.bbci.co.uk/news/world/asia/rss.xml'),
 ('Guardian Asia','亚洲','https://www.theguardian.com/world/asia/rss'),
 ('SCMP China','中国','https://www.scmp.com/rss/4/feed'),
 ('SCMP Hong Kong','中国','https://www.scmp.com/rss/2/feed'),
 ('CNA Asia','亚洲','https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6511'),
 ('CNA Singapore','亚洲','https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=10416'),
 ('CNA Business','商业经济','https://www.channelnewsasia.com/api/v1/rss-outbound-feed?_format=xml&category=6936'),
]
CATEGORIES=['全部','全球','中国','亚洲','商业经济','科技AI','科学环境']
KEYWORDS=[('war|conflict|ceasefire|invasion|战争|冲突',1.5),('election|president|government|parliament|选举|政府',1.1),('economy|inflation|central bank|interest rate|经济|通胀',1.1),('ai|artificial intelligence|chip|人工智能|芯片',.8),('earthquake|flood|typhoon|climate|地震|洪水|台风',1.0)]
def connect():
 c=sqlite3.connect(DB,check_same_thread=False);c.row_factory=sqlite3.Row;c.execute('PRAGMA journal_mode=WAL');c.execute('CREATE TABLE IF NOT EXISTS news(id TEXT PRIMARY KEY,title TEXT,summary TEXT,url TEXT,source TEXT,category TEXT,published TEXT,score REAL,reason TEXT,created TEXT)');c.execute('CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT)');c.commit();return c
def clean(x):return re.sub(r'\s+',' ',html.unescape(re.sub('<[^>]+>',' ',x or ''))).strip()
def get_text(el,*names):
 for name in names:
  node=el.find(name)
  if node is not None and node.text:return clean(node.text)
 return ''
def fetch_feed(name,cat,url):
 req=urllib.request.Request(url,headers={'User-Agent':'DailySignal/1.0 (RSS reader)'})
 with urllib.request.urlopen(req,timeout=12) as resp: raw=resp.read(2_000_000)
 root=ET.fromstring(raw)
 entries=root.findall('.//item') or root.findall('{http://www.w3.org/2005/Atom}entry')
 out=[]
 for e in entries[:40]:
  title=get_text(e,'title','{http://www.w3.org/2005/Atom}title')
  link=get_text(e,'link')
  if not link:
   ln=e.find('{http://www.w3.org/2005/Atom}link');link=ln.get('href','') if ln is not None else ''
  summary=get_text(e,'description','{http://purl.org/rss/1.0/modules/content/}encoded','{http://www.w3.org/2005/Atom}summary')[:460]
  published=get_text(e,'pubDate','{http://purl.org/dc/elements/1.1/}date','{http://www.w3.org/2005/Atom}published','{http://www.w3.org/2005/Atom}updated')
  try:
   dt=parsedate_to_datetime(published)
   if dt.tzinfo is None:dt=dt.replace(tzinfo=datetime.timezone.utc)
   iso=dt.astimezone(datetime.timezone.utc).isoformat()
  except: 
   try:iso=datetime.datetime.fromisoformat(published.replace('Z','+00:00')).isoformat()
   except:iso=datetime.datetime.now(datetime.timezone.utc).isoformat()
  if not title or not link.startswith('https://'):continue
  out.append(dict(id=hashlib.sha256(link.encode()).hexdigest()[:20],title=title,summary=summary,url=link,source=name,category=cat,published=iso))
 return out
def score(item):
 text=(item['title']+' '+item['summary']).lower();v=4.5;hits=[]
 for pattern,weight in KEYWORDS:
  if re.search(pattern,text,re.I):v+=weight;hits.append(pattern.split('|')[0])
 if item['category']=='全球':v+=.4
 if item['category']=='商业经济':v+=.2
 v=min(9.5,round(v,1))
 return v,('主题关键词与覆盖范围启发式估计' if hits else '基础新闻权重估计')+'；非事实评级'
def refresh():
 all_items=[];errors=[]
 for name,cat,url in FEEDS:
  try:all_items+=fetch_feed(name,cat,url)
  except Exception as exc:errors.append(name+': '+str(exc)[:110])
 now=datetime.datetime.now(datetime.timezone.utc)
 recent=[]
 for item in all_items:
  try:age=(now-datetime.datetime.fromisoformat(item['published'])).total_seconds()/3600
  except:age=0
  if -6<=age<=48:recent.append(item)
 # Deduplicate near-identical headlines in a conservative way.
 seen=set();filtered=[]
 for item in sorted(recent,key=lambda x:x['published'],reverse=True):
  norm=re.sub(r'\W+','',item['title'].lower())[:95]
  if norm in seen:continue
  seen.add(norm);filtered.append(item)
 with connect() as c:
  for item in filtered:
   s,r=score(item)
   c.execute('INSERT OR IGNORE INTO news VALUES (?,?,?,?,?,?,?,?,?,?)',(item['id'],item['title'],item['summary'],item['url'],item['source'],item['category'],item['published'],s,r,now.isoformat()))
  c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('last_refresh',now.isoformat()))
  c.execute('INSERT OR REPLACE INTO metadata VALUES (?,?)',('feed_errors',json.dumps(errors,ensure_ascii=False)))
  c.commit()
 return {'received':len(all_items),'recent':len(filtered),'errors':errors}
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw):super().__init__(*a,directory=str(ROOT/'web'),**kw)
 def json_response(self,obj,status=200):
  b=json.dumps(obj,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def do_GET(self):
  p=urllib.parse.urlsplit(self.path)
  if p.path=='/api/news':
   q=urllib.parse.parse_qs(p.query);category=q.get('category',['全部'])[0];query=q.get('q',[''])[0].strip();date=q.get('date',[''])[0];minscore=float(q.get('min_score',['0'])[0] or 0)
   sql='SELECT * FROM news WHERE score>=?';args=[minscore]
   if category in CATEGORIES and category!='全部':sql+=' AND category=?';args.append(category)
   if query:sql+=' AND (title LIKE ? OR summary LIKE ?)';args.extend(['%'+query+'%']*2)
   if date:sql+=' AND substr(published,1,10)=?';args.append(date)
   sql+=' ORDER BY score DESC,published DESC LIMIT 50'
   with connect() as c:
    rows=[dict(x) for x in c.execute(sql,args)];last=c.execute("SELECT value FROM metadata WHERE key='last_refresh'").fetchone();total=c.execute('SELECT COUNT(*) FROM news').fetchone()[0]
   return self.json_response({'items':rows,'last_refresh':last[0] if last else None,'total':total,'scoring':'基于关键词的透明启发式评分，非AI语义分析','translation':'当前版本保留原文标题与摘要，不自动翻译'})
  if p.path=='/api/health':return self.json_response({'ok':True,'service':'Daily Signal'})
  return super().do_GET()
if __name__=='__main__':
 if '--refresh' in __import__('sys').argv:
  print(json.dumps(refresh(),ensure_ascii=False,indent=2));raise SystemExit
 if os.environ.get('AUTO_REFRESH','0')=='1':
  def loop():
   while True:
    try:print('refresh',refresh(),flush=True)
    except Exception as e:print('refresh failed',e,flush=True)
    time.sleep(6*3600)
  threading.Thread(target=loop,daemon=True).start()
 print('Open http://localhost:'+str(PORT));ThreadingHTTPServer(('0.0.0.0',PORT),Handler).serve_forever()
