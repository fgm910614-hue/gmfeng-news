#!/usr/bin/env python3
"""GMFENG NEWS V2: RSS -> verified source links -> dedupe -> optional AI Chinese editorial -> static JSON."""
import os, json, datetime, re, hashlib, urllib.request, difflib, time
from pathlib import Path
from collections import Counter
from collector_core import FEEDS, fetch_feed, score as fallback_score

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'site/data/news.json'
NOW=datetime.datetime.now(datetime.timezone.utc)
KEY=os.getenv('OPENAI_API_KEY','').strip()
MODEL=os.getenv('OPENAI_MODEL','gpt-4.1-mini')
MAX_ITEMS=50

def normalized(title):
    t=re.sub(r'[^\w\s]',' ',title.lower())
    t=re.sub(r'\b(breaking|live|update|exclusive|report|latest|news)\b',' ',t)
    return ' '.join(t.split())

def is_duplicate(item, kept):
    a=normalized(item['title'])
    for other in kept:
        b=normalized(other['title'])
        if item['url'].split('?')[0]==other['url'].split('?')[0]: return True
        if len(a)>20 and len(b)>20 and difflib.SequenceMatcher(None,a,b).ratio()>=0.79: return True
    return False

def ai_edit(batch):
    if not KEY: return None
    payload={'model':MODEL,'temperature':0.1,'response_format':{'type':'json_object'},'messages':[
      {'role':'system','content':('你是严谨的中文新闻编辑。只根据提供的RSS标题与摘要处理，不补充未证实事实。'
        '输出JSON对象 {"items":[{"id":"...","title_zh":"...","summary_zh":"...","score":7.2,"reason":"..."}]}。'
        '逐条保留id。中文标题准确简洁；摘要50至110个汉字，不足信息可更短。'
        '评分0至10，依据公共影响范围、现实影响、长期意义、来源可信度、时效性；'
        '避免关键词堆叠虚高。仅凭RSS无法核实的争议表述用“据某媒体报道”。'
        '不要凭空添加日期、人物、数据、背景或引述。')},
      {'role':'user','content':json.dumps(batch,ensure_ascii=False)}]}
    req=urllib.request.Request('https://api.openai.com/v1/chat/completions',data=json.dumps(payload).encode(),headers={
      'Authorization':'Bearer '+KEY,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=95) as r: result=json.load(r)
    return json.loads(result['choices'][0]['message']['content']).get('items',[])

def main():
    all_items=[]; errors=[];successful=0
    for name,cat,url in FEEDS:
        try:
            got=fetch_feed(name,cat,url)
            all_items.extend(got);successful+=1
        except Exception as e: errors.append(f'{name}: {str(e)[:130]}')
    if successful<2: raise RuntimeError('成功新闻源不足2个；保留上一版数据')
    candidates=[]
    for x in all_items:
        try: age=(NOW-datetime.datetime.fromisoformat(x['published'])).total_seconds()/3600
        except Exception: continue
        if -6<=age<=36 and x.get('title') and x.get('summary') and x.get('url','').startswith('https://'):
            x['score'],x['reason']=fallback_score(x)
            candidates.append(x)
    candidates.sort(key=lambda x:(x['score'],x['published']),reverse=True)
    kept=[]
    for x in candidates:
        if not is_duplicate(x,kept): kept.append(x)
        if len(kept)>=90: break
    if not kept: raise RuntimeError('没有符合时效的新闻；保留旧数据')
    # Process a larger candidate pool, then select top 50 after editorial scoring.
    edited=0;mode='原文采集 + 规则评分（未启用 AI）'
    if KEY:
        mode='AI 中文编译 + AI 辅助评分'
        for i in range(0,len(kept),12):
            batch=[{'id':x['id'],'title':x['title'],'summary':x['summary'][:420],
                    'source':x['source'],'category':x['category'],'published':x['published']} for x in kept[i:i+12]]
            try:
                response=ai_edit(batch)
                by_id={r['id']:r for r in response if isinstance(r,dict) and 'id' in r}
                for x in kept[i:i+12]:
                    r=by_id.get(x['id'],{})
                    zh_title=str(r.get('title_zh','')).strip()
                    zh_summary=str(r.get('summary_zh','')).strip()
                    if zh_title and zh_summary:
                        x['title_zh']=zh_title[:180];x['summary_zh']=zh_summary[:500]
                        try: x['score']=round(max(0,min(10,float(r['score']))),1)
                        except (KeyError,ValueError,TypeError): pass
                        x['reason']=str(r.get('reason','AI 辅助评分'))[:160]
                        edited+=1
            except Exception as e:
                errors.append('AI batch '+str(i//12+1)+': '+str(e)[:180])
            time.sleep(.3)
    kept.sort(key=lambda x:(x['score'],x['published']),reverse=True)
    final=kept[:MAX_ITEMS]
    # Do not overwrite a previously healthy site with a tiny failed fetch.
    if len(final)<10 and OUT.exists(): raise RuntimeError('本次仅采集到少于10条；保留旧数据')
    payload={'items':final,'last_refresh':NOW.isoformat(),'last_success':NOW.isoformat(),
       'total_candidates':len(all_items),'deduplicated_candidates':len(kept),
       'published_count':len(final),'translated_count':sum(bool(x.get('title_zh')) for x in final),
       'source_count':len(set(x['source'] for x in final)),'mode':mode,
       'scoring':'AI 辅助评分（需人工判断）' if KEY else '关键词启发式评分，非AI语义分析',
       'feed_errors':errors}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    temp=OUT.with_suffix('.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(OUT)
    print('Published',len(final),'translated',payload['translated_count'],'sources',payload['source_count'],'errors',len(errors))

if __name__=='__main__':main()
