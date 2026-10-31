
#!/usr/bin/env python3
"""GMFENG NEWS V2 - Daily news collection and Chinese editing."""

import os
import json
import datetime
import re
import difflib
import time
import urllib.request
import urllib.error
from pathlib import Path

from collector_core import FEEDS, fetch_feed, score as fallback_score

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site/data/news.json"

NOW = datetime.datetime.now(datetime.timezone.utc)

KEY = os.getenv("OPENAI_API_KEY", "").strip()
MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

MAX_ITEMS = 50
MIN_ITEMS = 10


def normalized(title):
    text = re.sub(r"[^\w\s]", " ", title.lower())
    text = re.sub(
        r"\b(breaking|live|update|exclusive|report|latest|news)\b",
        " ",
        text,
    )
    return " ".join(text.split())


def is_duplicate(item, kept):
    title = normalized(item["title"])

    for other in kept:
        other_title = normalized(other["title"])

        if item["url"].split("?")[0] == other["url"].split("?")[0]:
            return True

        if (
            len(title) > 20
            and len(other_title) > 20
            and difflib.SequenceMatcher(
                None, title, other_title
            ).ratio() >= 0.79
        ):
            return True

    return False


def ai_edit(batch):
    if not KEY:
        raise RuntimeError("OPENAI_API_KEY is missing")

    system_prompt = (
        "你是一名严谨的中文国际新闻编辑。"
        "只根据提供的RSS标题和摘要处理新闻，不添加未经证实的信息。"
        '返回JSON对象，格式为：'
        '{"items":[{"id":"...",'
        '"title_zh":"...",'
        '"summary_zh":"...",'
        '"score":7.2,'
        '"reason":"..."}]}。'
        "必须逐条保留原始id。"
        "中文标题自然、准确、简洁。"
        "摘要建议50至110个汉字，信息不足时可以更短。"
        "评分范围0至10，综合公共影响、现实意义、"
        "长期价值、来源可信度和时效性。"
        "避免夸张标题、虚构事实、重复事件和情绪化判断。"
        "不得添加原文没有的人名、数字、日期或引述。"
    )

    payload = {
        "model": MODEL,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": json.dumps(batch, ensure_ascii=False),
            },
        ],
    }

    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=95) as response:
            result = json.load(response)

    except urllib.error.HTTPError as error:
        # Do not print response bodies: they may contain sensitive data.
        raise RuntimeError(
            f"OpenAI API HTTP {error.code}: {error.reason}"
        ) from None

    except urllib.error.URLError as error:
        raise RuntimeError(
            f"OpenAI API network error: {type(error.reason).__name__}"
        ) from None

    content = result["choices"][0]["message"]["content"]

    parsed = json.loads(content)

    items = parsed.get("items")

    if not isinstance(items, list):
        raise ValueError("AI response does not contain an items list")

    return items


def main():
    print("========== GMFENG NEWS ==========", flush=True)

    print(
        "OPENAI_API_KEY:",
        "configured" if KEY else "missing",
        flush=True,
    )

    print("AI model:", MODEL, flush=True)

    all_items = []
    errors = []
    successful_feeds = 0

    # 1. Collect RSS feeds
    for name, category, url in FEEDS:
        try:
            items = fetch_feed(name, category, url)
            all_items.extend(items)
            successful_feeds += 1

        except Exception as error:
            message = (
                f"RSS {name}: "
                f"{type(error).__name__}"
            )
            errors.append(message)
            print("WARNING:", message, flush=True)

    print(
        "RSS collection:",
        successful_feeds,
        "feeds,",
        len(all_items),
        "items",
        flush=True,
    )

    if successful_feeds < 2:
        raise RuntimeError(
            "Too few RSS feeds succeeded. Previous data preserved."
        )

    # 2. Filter recent news
    candidates = []

    for item in all_items:
        try:
            published = datetime.datetime.fromisoformat(
                item["published"]
            )

            if published.tzinfo is None:
                published = published.replace(
                    tzinfo=datetime.timezone.utc
                )

            age = (NOW - published).total_seconds() / 3600

        except (KeyError, TypeError, ValueError):
            continue

        if (
            -6 <= age <= 36
            and item.get("title")
            and item.get("summary")
            and item.get("url", "").startswith("https://")
        ):
            item["score"], item["reason"] = fallback_score(item)
            candidates.append(item)

    candidates.sort(
        key=lambda item: (
            item["score"],
            item["published"],
        ),
        reverse=True,
    )

    # 3. Remove duplicate news
    kept = []

    for item in candidates:
        if not is_duplicate(item, kept):
            kept.append(item)

        if len(kept) >= 90:
            break

    print(
        "After filtering and deduplication:",
        len(kept),
        flush=True,
    )

    if len(kept) < MIN_ITEMS:
        raise RuntimeError(
            "Too few qualified articles. Previous data preserved."
        )

    # 4. Translate and score with AI
    if not KEY:
        raise RuntimeError(
            "OPENAI_API_KEY missing. "
            "Chinese news update cancelled."
        )

    edited = 0

    for start in range(0, len(kept), 12):
        batch_items = kept[start:start + 12]

        batch = [
            {
                "id": item["id"],
                "title": item["title"],
                "summary": item["summary"][:420],
                "source": item["source"],
                "category": item["category"],
                "published": item["published"],
            }
            for item in batch_items
        ]

        batch_number = start // 12 + 1

        try:
            response = ai_edit(batch)

            by_id = {
                str(result["id"]): result
                for result in response
                if isinstance(result, dict)
                and "id" in result
            }

            batch_translated = 0

            for item in batch_items:
                result = by_id.get(str(item["id"]), {})

                title_zh = str(
                    result.get("title_zh") or ""
                ).strip()

                summary_zh = str(
                    result.get("summary_zh") or ""
                ).strip()

                if not title_zh or not summary_zh:
                    continue

                item["title_zh"] = title_zh[:180]
                item["summary_zh"] = summary_zh[:500]

                try:
                    item["score"] = round(
                        max(
                            0,
                            min(10, float(result["score"])),
                        ),
                        1,
                    )
                except (KeyError, ValueError, TypeError):
                    pass

                item["reason"] = str(
                    result.get("reason")
                    or "AI 辅助评分"
                )[:160]

                edited += 1
                batch_translated += 1

            print(
                f"AI batch {batch_number}: "
                f"translated {batch_translated}/{len(batch_items)}",
                flush=True,
            )

        except Exception as error:
            message = (
                f"AI batch {batch_number}: "
                f"{type(error).__name__}: {str(error)[:200]}"
            )

            errors.append(message)
            print("ERROR:", message, flush=True)

        time.sleep(0.3)

    print("Total translated:", edited, flush=True)

    # 5. Publish Chinese news only
    translated_items = [
        item for item in kept
        if item.get("title_zh") and item.get("summary_zh")
    ]

    translated_items.sort(
        key=lambda item: (
            item["score"],
            item["published"],
        ),
        reverse=True,
    )

    final = translated_items[:MAX_ITEMS]

    if len(final) < MIN_ITEMS:
        raise RuntimeError(
            f"Only {len(final)} Chinese articles available. "
            "Previous site data preserved. "
            "Check the AI errors above."
        )

    # 6. Save updated JSON
    completed_at = datetime.datetime.now(
        datetime.timezone.utc
    ).isoformat()

    payload = {
        "items": final,
        "last_refresh": completed_at,
        "last_success": completed_at,
        "total_candidates": len(all_items),
        "deduplicated_candidates": len(kept),
        "published_count": len(final),
        "translated_count": len(final),
        "source_count": len({
            item["source"] for item in final
        }),
        "mode": "AI 中文编译 + AI 辅助评分",
        "scoring": "AI 辅助评分（需人工判断）",
        "feed_errors": errors,
    }

    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp = OUT.with_suffix(".tmp")

    temp.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    temp.replace(OUT)

    print(
        "Published",
        len(final),
        "translated",
        payload["translated_count"],
        "sources",
        payload["source_count"],
        "errors",
        len(errors),
        flush=True,
    )

    print("GMFENG NEWS update completed.", flush=True)


if __name__ == "__main__":
    main()
