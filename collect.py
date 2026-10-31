#!/usr/bin/env python3
"""Fetch publicly available RSS and write a static JSON file. No third-party packages."""
import json,datetime,re
from pathlib import Path
from collector_core import FEEDS,fetch_feed,score
out=Path(__file__).parent/'site/data/news.json'
now=datetime.datetime.now(datetime.timezone.utc)
items=[];errors=[]
for name,cat,url in FEEDS:
 try: items.extend(fetch_feed(name,cat,url))
 except Exception as e: errors.append(name+': '+str(e)[:160])
seen=set();clean=[]
for item in sorted(items,key=lambda x:x['published'],reverse=True):
 try: age=(now-datetime.datetime.fromisoformat(item['published'])).total_seconds()/3600
 except Exception: continue
 if not -6<=age<=48:continue
 norm=re.sub(r'\W+','',item['title'].lower())[:95]
 if norm in seen:continue
 seen.add(norm);s,reason=score(item);item.update(score=s,reason=reason);clean.append(item)
clean.sort(key=lambda x:(x['score'],x['published']),reverse=True)
# Never overwrite valid previous data with an empty result due to network errors.
if not clean:
 print('No recent RSS items; preserve previous data. Errors:',errors)
 raise SystemExit(1)
payload={'items':clean[:50],'last_refresh':now.isoformat(),'scoring':'启发式规则评分，非AI语义分析','feed_errors':errors}
out.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Saved',len(payload['items']),'items; errors:',len(errors))
