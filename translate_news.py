"""Offline English-to-Chinese translation with Argos Translate.

No cloud API, account or billing. GitHub Actions downloads the open-source
model at run time. Source text is retained, and errors never stop publishing.
"""
import os
import re
from news_quality import polish_zh_title

MAX_TEXT_CHARS = 900
MAX_RUN_CHARS = max(0, int(os.getenv('TRANSLATION_MAX_CHARS', '18000')))
CJK = re.compile(r'[\u3400-\u9fff]')


def _load_translator():
    import argostranslate.package as package
    import argostranslate.translate as translate

    installed = translate.get_installed_languages()
    english = next((lang for lang in installed if lang.code == 'en'), None)
    chinese = next((lang for lang in installed if lang.code == 'zh'), None)
    if not (english and chinese):
        package.update_package_index()
        available = package.get_available_packages()
        model = next((p for p in available if p.from_code == 'en' and p.to_code == 'zh'), None)
        if model is None:
            raise RuntimeError('English-to-Chinese model not found')
        package.install_from_path(model.download())
        installed = translate.get_installed_languages()
        english = next((lang for lang in installed if lang.code == 'en'), None)
        chinese = next((lang for lang in installed if lang.code == 'zh'), None)
    if not (english and chinese):
        raise RuntimeError('English-to-Chinese model unavailable after installation')
    return english.get_translation(chinese)


def translate_items(items, previous=None):
    """Translate selected items in place. Returns (count, errors, characters).

    Previously translated records are reused when URL and source text match.
    If the offline model cannot be installed, originals remain intact.
    """
    old_items = (previous or {}).get('items', [])
    cache = {
        (old.get('url'), old.get('title'), old.get('summary')): old
        for old in old_items if isinstance(old, dict)
    }
    errors, count, used = [], 0, 0
    translator = None
    model_failed = False

    for item in items:
        title = str(item.get('title') or '').strip()
        summary = str(item.get('summary') or '').strip()
        old = cache.get((item.get('url'), title, summary), {})
        if old.get('title_zh') and (old.get('summary_zh') or not summary):
            item['title_zh'] = polish_zh_title(old['title_zh'])
            item['summary_zh'] = old.get('summary_zh', '')
            count += 1
            continue
        if not title:
            continue
        if CJK.search(title) and (not summary or CJK.search(summary)):
            item['title_zh'] = polish_zh_title(title)
            item['summary_zh'] = summary
            count += 1
            continue
        if model_failed:
            continue
        title_part = title[:MAX_TEXT_CHARS]
        summary_part = summary[:MAX_TEXT_CHARS]
        chars = len(title_part) + len(summary_part)
        if used + chars > MAX_RUN_CHARS:
            errors.append('Offline translation character budget reached; remaining articles keep originals')
            break
        try:
            if translator is None:
                translator = _load_translator()
            zh_title = translator.translate(title_part).strip()
            zh_summary = translator.translate(summary_part).strip() if summary_part else ''
            if not zh_title or not CJK.search(zh_title):
                raise ValueError('Translation produced no Chinese title')
            item['title_zh'] = polish_zh_title(zh_title)
            item['summary_zh'] = zh_summary
            count += 1
            used += chars
        except Exception as exc:
            errors.append(f'Offline translation error: {type(exc).__name__}: {str(exc)[:120]}')
            if translator is None:
                model_failed = True
            if len(errors) >= 5:
                errors.append('Too many translation errors; remaining articles keep originals')
                break
    return count, errors, used
