
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GMFENG NEWS - Stable RSS Collector
No OpenAI API required.
Output: site/data/news.json
"""

import datetime as dt
import difflib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from collector_core import FEEDS, fetch_feed, score as fallback_score
from translate_news import translate_items
from news_quality import editorial_score, region_for, topic_for, deduplicate


# ========== 基础配置 ==========

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "site" / "data" / "news.json"

MAX_ITEMS = 50
MAX_AGE_HOURS = 36
MIN_ITEMS = 10
MIN_SUCCESSFUL_FEEDS = 2

NOW = dt.datetime.now(dt.timezone.utc)


# ========== 通用工具 ==========

def parse_date(value):
    """将新闻发布时间转换为 UTC。"""
    if isinstance(value, dt.datetime):
        published = value
    elif isinstance(value, (int, float)):
        published = dt.datetime.fromtimestamp(
            value, tz=dt.timezone.utc
        )
    else:
        text = str(value or "").strip()
        if not text:
            return None

        try:
            published = dt.datetime.fromisoformat(
                text.replace("Z", "+00:00")
            )
        except ValueError:
            return None

    if published.tzinfo is None:
        published = published.replace(tzinfo=dt.timezone.utc)

    return published.astimezone(dt.timezone.utc)


def normalize_title(title):
    """标准化标题，用于去重。"""
    text = str(title or "").lower()
    text = re.sub(
        r"\b(breaking|live|update|exclusive|latest)\b",
        " ",
        text
    )
    text = re.sub(r"[^\w\s]", " ", text)
    return " ".join(text.split())


def canonical_url(url):
    """移除常见追踪参数，保留原始新闻地址。"""
    try:
        parts = urlsplit(str(url or "").strip())
        if parts.scheme not in ("http", "https"):
            return ""

        query = [
            (key, value)
            for key, value in parse_qsl(
                parts.query, keep_blank_values=True
            )
            if not key.lower().startswith("utm_")
            and key.lower() not in (
                "fbclid", "gclid", "mc_cid", "mc_eid"
            )
        ]

        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip("/") or "/",
            urlencode(query),
            ""
        ))
    except Exception:
        return ""


def is_duplicate(item, selected):
    """按链接和标题相似度去重。"""
    title = normalize_title(item.get("title"))
    url = canonical_url(item.get("url"))

    for other in selected:
        other_url = canonical_url(other.get("url"))
        other_title = normalize_title(other.get("title"))

        if url and url == other_url:
            return True

        if title and title == other_title:
            return True

        if len(title) >= 20 and len(other_title) >= 20:
            similarity = difflib.SequenceMatcher(
                None, title, other_title
            ).ratio()

            if similarity >= 0.79:
                return True

    return False


def calculate_score(item):
    """使用 collector_core.py 的原有评分规则。"""
    try:
        result = fallback_score(item)

        if isinstance(result, (list, tuple)):
            value = result[0]
            reason = result[1] if len(result) > 1 else ""
        else:
            value = result
            reason = ""

        value = round(
            max(0.0, min(10.0, float(value))), 1
        )

        return value, str(reason or "规则辅助评分")

    except Exception as exc:
        print(
            "WARNING: scoring failed:",
            str(exc)[:150],
            flush=True
        )
        return 5.0, "基础评分，需人工判断"


def read_previous():
    """读取上一版新闻，供异常检查使用。"""
    if not OUTPUT.exists():
        return None

    try:
        with OUTPUT.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict) and isinstance(
            data.get("items"), list
        ):
            return data
    except Exception as exc:
        print(
            "WARNING: previous JSON unreadable:",
            str(exc)[:150],
            flush=True
        )

    return None


def save_json(data):
    """原子写入，避免生成一半的 JSON 文件。"""
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(
        prefix="news_",
        suffix=".tmp",
        dir=str(OUTPUT.parent)
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                ensure_ascii=False,
                indent=2
            )
            file.write("\n")

        os.replace(temp_path, OUTPUT)

    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


# ========== 地域平衡（软目标，不降低新闻质量门槛） ==========

# 目标：50 条时中国约 12、亚洲其他地区约 13，其余全球约 25。
# 某区域不足时自动回填其他地区；这不是实际地域的强制配额。
REGION_TARGETS = {"中国": 10, "亚洲": 10, "欧洲": 9, "美洲": 9, "中东非洲": 8, "大洋洲": 4}
REGION_PATTERNS = [
 ("中国", r"中国|大陆|香港|澳门|台湾|深圳|北京|上海|China|Chinese|Hong Kong|Macau|Taiwan|Beijing|Shanghai|Shenzhen"),
 ("亚洲", r"亚洲|日本|韩国|印度|新加坡|越南|泰国|印尼|菲律宾|马来西亚|巴基斯坦|Japan|Korea|India|Singapore|Vietnam|Thailand|Indonesia|Philippines|Malaysia|Pakistan|Asia"),
 ("欧洲", r"欧洲|英国|法国|德国|意大利|西班牙|乌克兰|俄罗斯|欧盟|Europe|Britain|UK|France|Germany|Italy|Spain|Ukraine|Russia|European Union"),
 ("美洲", r"美国|加拿大|墨西哥|巴西|阿根廷|美国总统|美洲|United States|U\.S\.|USA|Canada|Mexico|Brazil|Argentina|Latin America|White House"),
 ("中东非洲", r"中东|非洲|以色列|加沙|伊朗|沙特|埃及|尼日利亚|南非|Middle East|Africa|Israel|Gaza|Iran|Saudi|Egypt|Nigeria|South Africa"),
 ("大洋洲", r"澳大利亚|新西兰|大洋洲|Australia|New Zealand|Oceania"),
]
REGION_PATTERNS = [(region,re.compile(pattern,re.I)) for region,pattern in REGION_PATTERNS]
REGIONAL_FEED_CATEGORIES = set(REGION_TARGETS)

def news_region(item):
    return region_for(item)[0]


def balanced_pick(items, limit):
    """先按地区软目标择优，再以全局最高分填满剩余位置。"""
    pools = {region: [] for region in REGION_TARGETS}
    pools["其他"] = []
    for item in items:
        region = news_region(item)
        item["region"] = region
        pools[region].append(item)
    chosen = []
    used = set()
    for region, target in REGION_TARGETS.items():
        for item in pools[region][:target]:
            if len(chosen) >= limit:
                break
            chosen.append(item)
            used.add(id(item))
    for item in items:
        if len(chosen) >= limit:
            break
        if id(item) not in used:
            chosen.append(item)
            used.add(id(item))
    # 页面仍按评分和时间展示，不按地区分块。
    chosen.sort(key=lambda item: (item["score"], item["published"]), reverse=True)
    return chosen


# ========== 新闻采集主程序 ==========

def main():
    print("========== GMFENG NEWS / RSS MODE ==========")
    print("Started:", NOW.isoformat())
    print("Offline translation:", "Argos Translate (no API key)")
    print(flush=True)

    previous = read_previous()

    all_items = []
    errors = []
    successful_feeds = 0

    # 1. 采集 RSS
    for name, category, feed_url in FEEDS:
        try:
            results = fetch_feed(
                name, category, feed_url
            )

            if not isinstance(results, list):
                results = list(results or [])

            all_items.extend(results)
            successful_feeds += 1

            print(
                "OK:", name,
                "items:", len(results),
                flush=True
            )

        except Exception as exc:
            message = f"{name}: {type(exc).__name__}: {exc}"
            errors.append(message[:250])
            print(
                "WARNING:", message[:250],
                flush=True
            )

    print(
        "RSS collection:",
        successful_feeds,
        "feeds,",
        len(all_items),
        "items",
        flush=True
    )

    if successful_feeds < MIN_SUCCESSFUL_FEEDS:
        raise RuntimeError(
            "Too few successful RSS feeds. "
            "Previous site data preserved."
        )

    # 2. 过滤无效及过期新闻
    candidates = []

    for raw in all_items:
        if not isinstance(raw, dict):
            continue

        item = dict(raw)

        title = str(item.get("title") or "").strip()
        summary = str(
            item.get("summary")
            or item.get("description")
            or ""
        ).strip()

        url = str(item.get("url") or "").strip()

        published = parse_date(
            item.get("published")
            or item.get("pubDate")
            or item.get("date")
        )

        if not title or not url or published is None:
            continue

        if not canonical_url(url):
            continue

        age_hours = (
            NOW - published
        ).total_seconds() / 3600

        if not -6 <= age_hours <= MAX_AGE_HOURS:
            continue

        item["title"] = title
        item["summary"] = summary
        item["url"] = url
        item["published"] = published.isoformat()

        item["source"] = str(
            item.get("source") or "未知来源"
        )

        item["category"] = str(
            item.get("category") or "综合"
        )

        item["score"], item["reason"] = editorial_score(item)
        item["topic"] = topic_for(item)
        item["region_confidence"] = region_for(item)[1]

        candidates.append(item)

    print(
        "Valid recent candidates:",
        len(candidates),
        flush=True
    )

    # 3. 高置信度跨媒体事件去重；保留分数最高的代表报道。
    candidates.sort(key=lambda item: (item["score"], item["published"]), reverse=True)
    selected, dedup_stats = deduplicate(candidates)
    print("After deduplication:", len(selected), flush=True)
    print("Deduplication reasons:", dedup_stats, flush=True)

    # 4. 选取最多 50 条
    final_items = balanced_pick(selected, MAX_ITEMS)
    region_counts = {region: sum(x["region"] == region for x in final_items) for region in REGION_TARGETS}
    region_counts["其他"] = sum(x["region"] == "其他" for x in final_items)
    print("Region distribution:", region_counts, flush=True)

    if len(final_items) < MIN_ITEMS:
        raise RuntimeError(
            f"Only {len(final_items)} valid articles. "
            "Previous site data preserved."
        )

    # 5. 可选中文翻译；失败时保留英文原文，不影响发布。
    translated_count, translation_errors, translation_chars = translate_items(
        final_items, previous
    )
    print("Translation chars submitted:", translation_chars, flush=True)
    for message in translation_errors:
        print("WARNING:", message, flush=True)

    # 6. 输出网站数据
    sources = {
        item["source"] for item in final_items
    }

    payload = {
        "items": final_items,
        "last_refresh": NOW.isoformat(),
        "last_success": NOW.isoformat(),
        "total_candidates": len(all_items),
        "deduplicated_candidates": len(selected),
        "published_count": len(final_items),
        "translated_count": translated_count,
        "translation_characters": translation_chars,
        "translation_errors": translation_errors,
        "source_count": len(sources),
        "region_counts": region_counts,
        "deduplication_stats": dedup_stats,
        "quality_version": "editorial-rules-v1",
        "mode": "RSS 自动采集 + Argos 离线中文翻译",
        "scoring": "可解释的公共事件优先级规则，非事实可信度评级；不使用付费 AI",
        "feed_errors": errors,
        "configured_feeds": len(FEEDS),
        "successful_feeds": successful_feeds
    }

    save_json(payload)

    print()
    print("========== UPDATE SUCCESS ==========")
    print("Published:", len(final_items))
    print("Translated:", payload["translated_count"])
    print("Sources:", len(sources))
    print("Feed errors:", len(errors))
    print("Last refresh:", payload["last_refresh"])
    print("Output:", OUTPUT)
    print("====================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(
            "ERROR:",
            type(exc).__name__,
            str(exc),
            file=sys.stderr,
            flush=True
        )
        sys.exit(1)
