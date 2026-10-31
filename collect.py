import os
import json
import re
import difflib
import datetime as dt
import time
import hashlib
import urllib.request
from pathlib import Path
from collections import Counter

def is_duplicate(item, selected):
    a = normalize_title(item['title'])
    url = canonical_url(item['url'])
    for other in selected:
        if url == canonical_url(other['url']):
            return True
        b = normalize_title(other['title'])
        if len(a) > 20 and len(b) > 20 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.79:
            return True
    return False


def parse_date(value):
    if isinstance(value, dt.datetime):
        published = value
    else:
        published = dt.datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if published.tzinfo is None:
        published = published.replace(tzinfo=dt.timezone.utc)
    return published.astimezone(dt.timezone.utc)


def main():
    started = dt.datetime.now(dt.timezone.utc)
    print('========== GMFENG NEWS / RSS MODE ==========', flush=True)
    all_items, errors = [], []
    successful_feeds = 0
    for name, category, url in FEEDS:
        try:
            items = fetch_feed(name, category, url)
            if not isinstance(items, list):
                raise ValueError('Feed did not return a list')
            all_items.extend(items)
            successful_feeds += 1
        except Exception as exc:
            message = f'RSS {name}: {type(exc).__name__}: {str(exc)[:120]}'
            errors.append(message)
            print('WARNING:', message, flush=True)

    print(f'RSS collection: {successful_feeds} feeds, {len(all_items)} items', flush=True)
    if successful_feeds < 2:
        raise RuntimeError('Too few feeds succeeded; previous site data preserved.')

    candidates = []
    for raw in all_items:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        if not all(item.get(k) for k in ('title', 'summary', 'url', 'published', 'source')):
            continue
        if not str(item['url']).startswith('https://'):
            continue
        try:
            published = parse_date(item['published'])
            age_hours = (started - published).total_seconds() / 3600
            if not -6 <= age_hours <= MAX_AGE_HOURS:
                continue
            value, reason = fallback_score(item)
            item['score'] = round(max(0.0, min(10.0, float(value))), 1)
            item['reason'] = str(reason)
            item['published'] = published.isoformat()
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            continue
        # Prevent stale AI translations from being mistaken for current editorial output.
        item.pop('title_zh', None)
        item.pop('summary_zh', None)
        candidates.append(item)

    candidates.sort(key=lambda x: (x['score'], x['published']), reverse=True)
    selected = []
    for item in candidates:
        if not is_duplicate(item, selected):
            selected.append(item)
        if len(selected) >= MAX_ITEMS:
            break

    if len(selected) < MIN_ITEMS:
        raise RuntimeError(f'Only {len(selected)} qualified articles; previous site data preserved.')

    completed = dt.datetime.now(dt.timezone.utc).isoformat()
    payload = {
        'items': selected,
        'last_refresh': completed,
        'last_success': completed,
        'total_candidates': len(all_items),
        'deduplicated_candidates': len(selected),
        'published_count': len(selected),
        'translated_count': 0,
        'source_count': len({str(x['source']) for x in selected}),
        'mode': 'RSS 原文采集（暂不使用 AI 翻译）',
        'scoring': '关键词启发式评分，仅供参考',
        'feed_errors': errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temp = OUT.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(OUT)
    print(f"Published {len(selected)} translated 0 sources {payload['source_count']} errors {len(errors)}", flush=True)
    print('GMFENG NEWS update completed.', flush=True)


if __name__ == '__main__':
    main()
