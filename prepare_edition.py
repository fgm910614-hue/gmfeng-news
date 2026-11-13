"""Polish known names and keep a bounded set of first-party lead image copies."""
import hashlib
import io
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageOps

IMAGE_HOSTS = {
    "s.france24.com", "i.guim.co.uk", "ichef.bbci.co.uk", "i.dawn.com",
    "cdn.i-scmp.com", "cdn.arstechnica.net", "dam.mediacorp.sg",
    "live-production.wcms.abc-cdn.net.au", "www.aljazeera.com",
}

HEADLINES = {
    "Jensen Huang resigns as Nvidia CEO after mounting scandals": "黄仁勋辞任英伟达首席执行官",
    "Jensen Huang resigns as Nvidia CEO after alleged affairs": "黄仁勋辞任英伟达首席执行官",
    "Jensen Huang steps down as Nvidia CEO after reports of extramarital affairs": "黄仁勋辞任英伟达首席执行官",
    "Nvidia CEO Jensen Huang resigns after revelations on extramarital affairs": "黄仁勋辞任英伟达首席执行官",
    "Nvidia董事會宣佈黃仁勳辭任執行長": "英伟达董事会宣布黄仁勋辞任首席执行官",
    "Who is Nvidia interim CEO Colette Kress?": "英伟达临时首席执行官科莱特·克雷斯是谁？",
    "Jensen Huang’s departure may signal tighter US controls on AI chip exports to China": "黄仁勋离任后，美国会收紧对华 AI 芯片出口管制吗？",
    "Nvidia’s hunt for Jensen Huang’s successor: insiders, rivals and a Trump pick": "谁会接替黄仁勋？英伟达继任人选引发讨论",
    "黃仁勳辭輝達執行長 川普喊話：庫克應接任": "特朗普谈英伟达接班人选，称库克应接任",
    "Nvidia’s Huang ousted by board in move that roils AI economy": "黄仁勋离任，英伟达管理层变动波及 AI 产业",
}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


def cache_photo(url, directory, day):
    try:
        parsed = urlsplit(url)
        if (parsed.scheme != "https" or parsed.hostname not in IMAGE_HOSTS
                or parsed.username or parsed.password or parsed.port):
            return None
        request = urllib.request.Request(url, headers={"User-Agent": "GMFENG News/1.0"})
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=8) as response:
            data = response.read(5_000_001)
        if len(data) > 5_000_000:
            return None
        with Image.open(io.BytesIO(data)) as original:
            if min(original.size) < 120 or original.width * original.height > 24_000_000:
                return None
            picture = ImageOps.exif_transpose(original).convert("RGB")
            picture.thumbnail((1100, 800))
            output = io.BytesIO()
            picture.save(output, "WEBP", quality=78)
        content = output.getvalue()
        name = day + "-" + hashlib.sha256(content).hexdigest()[:16] + ".webp"
        (directory / name).write_bytes(content)
        return "/images/daily/" + name
    except (OSError, ValueError, Image.DecompressionBombError):
        return None


def prepare_edition(items, site, day):
    directory = site / "images" / "daily"
    directory.mkdir(parents=True, exist_ok=True)
    urls = []
    for item in items:
        if item["title"] in HEADLINES:
            item["title_zh"] = HEADLINES[item["title"]]
        for key in ("title_zh", "summary_zh"):
            if item.get(key):
                value = re.sub(r"Jensen\\s+Huang|黃仁勳|詹森\\s*黄先生", "黄仁勋", item[key], flags=re.I)
                item[key] = re.sub(r"NVIDIA|恩维迪亚|輝達|英偉達", "英伟达", value, flags=re.I)
        url = item.get("image")
        if url and url not in urls and len(urls) < 8 and url.startswith("https://"):
            urls.append(url)
    with ThreadPoolExecutor(max_workers=4) as pool:
        cached = dict(zip(urls, pool.map(lambda url: cache_photo(url, directory, day), urls)))
    for item in items:
        if cached.get(item.get("image")):
            item["image_original"] = item["image"]
            item["image"] = cached[item["image"]]
    keep = {Path(item["image"]).name for item in items if (item.get("image") or "").startswith("/images/daily/")}
    for photo in sorted(directory.glob("*.webp"), reverse=True)[64:]:
        if photo.name not in keep:
            photo.unlink()
    print("Cached edition photos:", sum(bool(value) for value in cached.values()))
