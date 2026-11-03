"""Optional Google Cloud Translation Basic v2 integration.

Uses GOOGLE_TRANSLATE_API_KEY stored in GitHub Actions Secrets. No third-party
Python packages required. Source titles and summaries are always preserved.
"""
import json
import html
import os
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ENDPOINT = 'https://translation.googleapis.com/language/translate/v2'
MAX_TEXT_CHARS = 1500
MAX_RUN_CHARS = int(os.getenv('TRANSLATION_MAX_CHARS', '450000'))
CJK = re.compile(r'[\u3400-\u9fff]')


def _translate_pair(title, summary, api_key):
    texts = [title[:MAX_TEXT_CHARS], summary[:MAX_TEXT_CHARS]]
    body = json.dumps({'q': texts, 'target': 'zh-CN', 'format': 'text'}, ensure_ascii=False).encode('utf-8')
    request = Request(ENDPOINT + '?key=' + api_key, data=body, headers={'Content-Type': 'application/json'}, method='POST')
    with urlopen(request, timeout=20) as response:
        data = json.load(response)
    translations = data['data']['translations']
    if len(translations) != 2:
        raise ValueError('Unexpected translation response')
    return html.unescape(translations[0]['translatedText']), html.unescape(translations[1]['translatedText'])


def translate_items(items, previous=None):
    """Mutates selected news items; returns (translated_count, errors, chars_sent).

    Reuses previous Chinese text only when the English source text matches.
    Caps the total characters sent in a single run; no key means safe fallback.
    """
    key = os.getenv('GOOGLE_TRANSLATE_API_KEY', '').strip()
    previous_items = (previous or {}).get('items', [])
    cache = {}
    for old in previous_items:
        if not isinstance(old, dict):
            continue
        cache[(old.get('url'), old.get('title'), old.get('summary'))] = old

    errors = []
    used = 0
    translated = 0
    for item in items:
        title = str(item.get('title') or '').strip()
        summary = str(item.get('summary') or '').strip()
        old = cache.get((item.get('url'), title, summary), {})
        if old.get('title_zh') and (old.get('summary_zh') or not summary):
            item['title_zh'] = old['title_zh']
            item['summary_zh'] = old.get('summary_zh', '')
            translated += 1
            continue

        if not key:
            continue
        if not title or not summary:
            # Preserve incomplete records without inventing a Chinese summary.
            continue
        if CJK.search(title) and CJK.search(summary):
            item['title_zh'] = title
            item['summary_zh'] = summary
            translated += 1
            continue
        count = len(title[:MAX_TEXT_CHARS]) + len(summary[:MAX_TEXT_CHARS])
        if used + count > MAX_RUN_CHARS:
            errors.append('Reached translation character safety limit')
            break
        # Reserve before request to avoid unbounded retries/cost on failures.
        used += count
        try:
            translated_title, translated_summary = _translate_pair(title, summary, key)
            if not translated_title.strip() or not translated_summary.strip():
                raise ValueError('Empty translated title or summary')
            item['title_zh'] = translated_title
            item['summary_zh'] = translated_summary
            translated += 1
        except (HTTPError, URLError, TimeoutError, ValueError, KeyError, OSError) as exc:
            # Never log the URL, because it contains the secret API key.
            errors.append(f'Translation failed for item {len(errors)+1}: {type(exc).__name__}')
            if isinstance(exc, HTTPError) and exc.code in (400, 401, 403, 429):
                errors.append('Translation service rejected request or quota; remaining items use original text')
                break
            if len(errors) >= 5:
                errors.append('Too many translation failures; remaining items use original text')
                break
        time.sleep(0.1)
    return translated, errors, used
