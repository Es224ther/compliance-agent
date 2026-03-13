from __future__ import annotations

import html
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REG_DIR = ROOT / "data" / "regulations"
SOURCE_DIR = REG_DIR / "_sources"


SOURCE_MAP = {
    "https://gdpr.verasafe.com/wp-json/wp/v2/pages?per_page=100&page=1": SOURCE_DIR / "gdpr_pages.json",
    "https://gdpr.verasafe.com/wp-json/wp/v2/pages?slug=article-1": SOURCE_DIR / "gdpr_article1.json",
    "https://artificialintelligenceact.eu/wp-json/wp/v2/chapter?per_page=30": SOURCE_DIR / "eu_ai_act_chapters.json",
    "https://artificialintelligenceact.eu/wp-json/wp/v2/article?per_page=100&page=1": SOURCE_DIR / "eu_ai_act_articles_page1.json",
    "https://artificialintelligenceact.eu/wp-json/wp/v2/article?per_page=100&page=2": SOURCE_DIR / "eu_ai_act_articles_page2.json",
    "https://artificialintelligenceact.eu/wp-json/wp/v2/annex?per_page=20": SOURCE_DIR / "eu_ai_act_annexes.json",
    "https://www.stats.gov.cn/gk/tjfg/xgfxfg/202503/t20250310_1958923.html": SOURCE_DIR / "pipl_stats.html",
    "https://www.stats.gov.cn/gk/tjfg/xgfxfg/202503/t20250310_1958928.html": SOURCE_DIR / "dsl_stats.html",
    "https://www.cac.gov.cn/2016-11/07/c_1119867116.htm": SOURCE_DIR / "csl_page1.html",
    "https://www.cac.gov.cn/2016-11/07/c_1119867116_2.htm": SOURCE_DIR / "csl_page2.html",
    "https://www.cac.gov.cn/2016-11/07/c_1119867116_3.htm": SOURCE_DIR / "csl_page3.html",
    "https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm": SOURCE_DIR / "aigc_marking.html",
}


GDPR_CHAPTERS = [
    (1, 4, "Chapter I: General provisions"),
    (5, 11, "Chapter II: Principles"),
    (12, 23, "Chapter III: Rights of the data subject"),
    (24, 43, "Chapter IV: Controller and processor"),
    (44, 50, "Chapter V: Transfers of personal data to third countries or international organisations"),
    (51, 59, "Chapter VI: Independent supervisory authorities"),
    (60, 76, "Chapter VII: Cooperation and consistency"),
    (77, 84, "Chapter VIII: Remedies, liability and penalties"),
    (85, 91, "Chapter IX: Provisions relating to specific processing situations"),
    (92, 93, "Chapter X: Delegated acts and implementing acts"),
    (94, 99, "Chapter XI: Final provisions"),
]


CN_CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百]+章")
CN_ARTICLE_RE = re.compile(r"^第[一二三四五六七八九十百零〇两\d]+条")


def fetch_text(url: str) -> str:
    path = SOURCE_MAP.get(url)
    if path is None or not path.exists():
        raise RuntimeError(f"Missing local source cache for {url}")
    return path.read_text(encoding="utf-8")


def fetch_json(url: str):
    return json.loads(fetch_text(url))


def strip_html(value: str) -> str:
    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    value = re.sub(r"</p>", "\n", value, flags=re.I)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = value.replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def extract_ps(html_text: str, pattern: str) -> list[str]:
    match = re.search(pattern, html_text, flags=re.S)
    if not match:
        raise RuntimeError("Failed to locate regulation body")
    body = match.group(1)
    paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", body, flags=re.S | re.I)
    result = []
    for paragraph in paragraphs:
        text = strip_html(paragraph)
        if text:
            result.append(text)
    return result


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_markdown(path: Path, meta: dict[str, str], lines: list[str]) -> None:
    header = [
        "<!-- ",
        f"regulation: {meta['regulation']}",
        f"jurisdiction: {meta['jurisdiction']}",
        f"language: {meta['language']}",
        f"version: {meta['version']}",
        f"effective_date: {meta['effective_date']}",
        "-->",
        "",
    ]
    text = "\n".join(header + lines).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")


def gdpr_chapter(article_no: int) -> str:
    for start, end, title in GDPR_CHAPTERS:
        if start <= article_no <= end:
            return title
    raise RuntimeError(f"Unknown GDPR article number: {article_no}")


def build_gdpr() -> None:
    pages = fetch_json("https://gdpr.verasafe.com/wp-json/wp/v2/pages?per_page=100&page=1")
    pages.extend(fetch_json("https://gdpr.verasafe.com/wp-json/wp/v2/pages?slug=article-1"))
    articles = []
    for page in pages:
        slug = page.get("slug", "")
        if not re.fullmatch(r"article-\d+", slug):
            continue
        match = re.match(r"Article (\d+) \| EU GDPR \| (.+)", page["title"]["rendered"])
        if not match:
            raise RuntimeError(f"Unexpected GDPR title: {page['title']['rendered']}")
        number = int(match.group(1))
        title = match.group(2).strip()
        content = strip_html(page["content"]["rendered"])
        articles.append((number, title, content))
    articles.sort(key=lambda item: item[0])

    lines: list[str] = []
    current_chapter = ""
    for number, title, content in articles:
        chapter = gdpr_chapter(number)
        if chapter != current_chapter:
            lines.append(f"# {chapter}")
            current_chapter = chapter
        lines.append(f"## Article {number}: {title}")
        lines.extend(content.splitlines())

    write_markdown(
        REG_DIR / "eu" / "gdpr_full.md",
        {
            "regulation": "GDPR",
            "jurisdiction": "EU",
            "language": "en",
            "version": "2016/679",
            "effective_date": "2018-05-25",
        },
        lines,
    )


def build_ai_act() -> None:
    chapters = fetch_json("https://artificialintelligenceact.eu/wp-json/wp/v2/chapter?per_page=30")
    article_to_chapter: dict[int, str] = {}
    for chapter in chapters:
        title = strip_html(chapter["title"]["rendered"]).replace("\n", " ").strip()
        for article_id in chapter["meta_box"].get("title-article_to", []):
            article_to_chapter[int(article_id)] = title

    articles: list[dict] = []
    for page_no in (1, 2):
        batch = fetch_json(f"https://artificialintelligenceact.eu/wp-json/wp/v2/article?per_page=100&page={page_no}")
        articles.extend(batch)

    normalized = []
    for article in articles:
        match = re.match(r"Article (\d+): (.+)", strip_html(article["title"]["rendered"]))
        if not match:
            continue
        article_no = int(match.group(1))
        title = match.group(2).strip()
        content = strip_html(article["content"]["rendered"])
        chapter = article_to_chapter.get(article["id"], "")
        normalized.append((article_no, title, chapter, content))
    normalized.sort(key=lambda item: item[0])

    lines: list[str] = []
    current_chapter = ""
    for article_no, title, chapter, content in normalized:
        if chapter and chapter != current_chapter:
            lines.append(f"# {chapter}")
            current_chapter = chapter
        lines.append(f"## Article {article_no}: {title}")
        lines.extend(content.splitlines())

    annexes = fetch_json("https://artificialintelligenceact.eu/wp-json/wp/v2/annex?per_page=20")
    if annexes:
        lines.append("# Annexes")
    for annex in sorted(annexes, key=lambda item: int(item["meta_box"]["item_order"])):
        title = strip_html(annex["title"]["rendered"]).replace("\n", " ").strip()
        content = strip_html(annex["content"]["rendered"])
        lines.append(f"# {title}")
        lines.extend(content.splitlines())

    write_markdown(
        REG_DIR / "eu" / "eu_ai_act_full.md",
        {
            "regulation": "EU AI Act",
            "jurisdiction": "EU",
            "language": "en",
            "version": "2024/1689",
            "effective_date": "2024-08-01",
        },
        lines,
    )


def build_cn_from_stats(url: str, out_path: Path, meta: dict[str, str]) -> None:
    html_text = fetch_text(url)
    paragraphs = extract_ps(html_text, r'<div class="trs_editor_view.*?">(.*?)</div>')
    lines: list[str] = []
    current_chapter = ""
    started = False
    in_toc = False
    skipped_first_chapter = False
    for paragraph in paragraphs:
        paragraph = paragraph.replace("　", "").strip()
        if not paragraph:
            continue
        if paragraph == "目录":
            in_toc = True
            continue
        if in_toc and not paragraph.startswith("第一章"):
            continue
        if in_toc and paragraph.startswith("第一章") and not skipped_first_chapter:
            skipped_first_chapter = True
            continue
        if in_toc and paragraph.startswith("第一章") and skipped_first_chapter:
            in_toc = False
        if CN_CHAPTER_RE.match(paragraph):
            current_chapter = paragraph
            started = True
            lines.append(f"# {paragraph}")
            continue
        if not started:
            continue
        if CN_ARTICLE_RE.match(paragraph):
            title, body = split_cn_article(paragraph)
            lines.append(f"## {title}")
            if body:
                lines.append(body)
            continue
        if lines and lines[-1].startswith("## "):
            lines.append(paragraph)
        elif current_chapter:
            lines.append(paragraph)

    write_markdown(out_path, meta, lines)


def split_cn_article(text: str) -> tuple[str, str]:
    match = re.match(r"^(第[一二三四五六七八九十百零〇两\d]+条)\s*(.*)$", text)
    if not match:
        return text, ""
    return match.group(1), match.group(2).strip()


def build_csl() -> None:
    base = "https://www.cac.gov.cn/2016-11/07/c_1119867116"
    pages = [fetch_text(f"{base}.htm")]
    for suffix in ("_2.htm", "_3.htm"):
        pages.append(fetch_text(f"{base}{suffix}"))

    lines: list[str] = []
    current_chapter = ""
    for html_text in pages:
        if "<DIV id=BodyLabel>" in html_text:
            paragraphs = extract_ps(html_text, r"<DIV id=BodyLabel>(.*?)</DIV>")
        else:
            start = html_text.index('<div id="content">')
            end = html_text.index('<!-- footer -->', start)
            paragraphs = []
            for paragraph in re.findall(r"<p[^>]*>(.*?)</p>", html_text[start:end], flags=re.S | re.I):
                text = strip_html(paragraph)
                if text:
                    paragraphs.append(text)
        for paragraph in paragraphs:
            paragraph = paragraph.replace("　", "").strip()
            if not paragraph or paragraph in {"新华社北京11月7日电", "目 录", "目　录"}:
                continue
            if CN_CHAPTER_RE.match(paragraph):
                if paragraph != current_chapter:
                    current_chapter = paragraph
                    lines.append(f"# {paragraph}")
                continue
            if CN_ARTICLE_RE.match(paragraph):
                title, body = split_cn_article(paragraph)
                lines.append(f"## {title}")
                if body:
                    lines.append(body)
                continue
            if lines and lines[-1].startswith("## "):
                lines.append(paragraph)

    write_markdown(
        REG_DIR / "cn" / "csl_full.md",
        {
            "regulation": "CSL",
            "jurisdiction": "CN",
            "language": "zh",
            "version": "2016",
            "effective_date": "2017-06-01",
        },
        lines,
    )


def build_aigc_marking() -> None:
    html_text = fetch_text("https://www.cac.gov.cn/2025-03/14/c_1743654684782215.htm")
    paragraphs = extract_ps(html_text, r"<DIV id=BodyLabel>(.*?)<div id=\"网站群管理\">")

    lines: list[str] = []
    started = False
    for paragraph in paragraphs:
        paragraph = paragraph.replace("　", "").strip()
        if not paragraph:
            continue
        if paragraph == "人工智能生成合成内容标识办法":
            started = True
            continue
        if not started:
            continue
        if CN_ARTICLE_RE.match(paragraph):
            title, body = split_cn_article(paragraph)
            lines.append(f"## {title}")
            if body:
                lines.append(body)
            continue
        if lines and lines[-1].startswith("## "):
            lines.append(paragraph)

    write_markdown(
        REG_DIR / "cn" / "aigc_marking_full.md",
        {
            "regulation": "AIGC Marking Measures",
            "jurisdiction": "CN",
            "language": "zh",
            "version": "2025",
            "effective_date": "2025-09-01",
        },
        lines,
    )


def main() -> None:
    ensure_dir(REG_DIR / "eu")
    ensure_dir(REG_DIR / "cn")
    build_gdpr()
    build_ai_act()
    build_cn_from_stats(
        "https://www.stats.gov.cn/gk/tjfg/xgfxfg/202503/t20250310_1958923.html",
        REG_DIR / "cn" / "pipl_full.md",
        {
            "regulation": "PIPL",
            "jurisdiction": "CN",
            "language": "zh",
            "version": "2021",
            "effective_date": "2021-11-01",
        },
    )
    build_cn_from_stats(
        "https://www.stats.gov.cn/gk/tjfg/xgfxfg/202503/t20250310_1958928.html",
        REG_DIR / "cn" / "dsl_full.md",
        {
            "regulation": "DSL",
            "jurisdiction": "CN",
            "language": "zh",
            "version": "2021",
            "effective_date": "2021-09-01",
        },
    )
    build_csl()
    build_aigc_marking()


if __name__ == "__main__":
    main()
