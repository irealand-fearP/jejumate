"""제주대학교 통합검색 결과를 공식 RAG 문서로 증분 색인한다."""
from __future__ import annotations

import html
import re
import ssl
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from app.data.jejunu_official import JejunuOfficialDocument
from app.services.jejunu_official_ingest import seed_jejunu_official_documents


SEARCH_API_URL = "https://www.jejunu.ac.kr/api/search"
OFFICIAL_SITE_URL = "https://www.jejunu.ac.kr"
CMS_SITE_URL = "https://cms.jejunu.ac.kr"
SEARCH_TYPE_ALL = 31
DEFAULT_RESULT_LIMIT = 3
REQUEST_TIMEOUT_SECONDS = 8.0
INTERMEDIATE_CA_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "certs"
    / "sectigo_rsa_domain_validation_secure_server_ca.pem"
)


class _NoticeTextExtractor(HTMLParser):
    """공지 본문의 표와 문단 경계를 보존하면서 텍스트만 추출한다."""

    _BLOCK_TAGS = {"br", "div", "li", "p", "table", "td", "th", "tr"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self.parts.append("\n- ")
        elif tag == "br":
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _NoticeTextExtractor()
    parser.feed(value or "")
    parser.close()
    lines = []
    for line in "".join(parser.parts).replace("\xa0", " ").splitlines():
        normalized = re.sub(r"[ \t]+", " ", html.unescape(line)).strip()
        if normalized:
            lines.append(normalized)
    return "\n".join(lines)


def build_official_search_query(question: str) -> str:
    """대화형 질문을 제주대 통합검색이 잘 찾는 핵심 명사형 검색어로 바꾼다."""
    compact = re.sub(r"\s+", "", question).lower()
    if any(keyword in compact for keyword in ("주차", "차량", "자동차")) and any(
        keyword in compact for keyword in ("등록", "정기이용", "해지", "주차증")
    ):
        return "자동차 정기이용"

    value = re.sub(r"제주(?:대학교|대)", " ", question, flags=re.IGNORECASE)
    value = re.sub(r"[^0-9A-Za-z가-힣]+", " ", value)
    for phrase in (
        "알려 주세요",
        "알려주세요",
        "알려 줘",
        "알려줘",
        "어떻게 해",
        "어떻게",
        "어디에서",
        "어디서",
        "어디에",
        "언제까지",
        "언제야",
        "궁금해",
        "할 수 있어",
        "할수있어",
    ):
        value = value.replace(phrase, " ")

    stopwords = {"관련", "문의", "방법", "좀", "해", "줘", "인가요", "이야", "야"}
    tokens: list[str] = []
    for raw_token in value.split():
        token = re.sub(r"(에서는|에서|으로는|으로|에게|까지|부터|은|는|이|가|을|를|로)$", "", raw_token)
        if len(token) >= 2 and token not in stopwords:
            tokens.append(token)
    return " ".join(tokens[:6]).strip()


@lru_cache(maxsize=1)
def _jejunu_ssl_context() -> ssl.SSLContext:
    """제주대 서버가 누락한 Sectigo 중간 인증서만 보완해 TLS 검증을 유지한다."""
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=str(INTERMEDIATE_CA_PATH))
    return context


def _request_json(params: dict[str, str | int]) -> dict[str, Any]:
    response = httpx.get(
        SEARCH_API_URL,
        params=params,
        headers={"User-Agent": "Jejumate-RAG/1.0 (+https://snp.rtvoice.com)"},
        timeout=REQUEST_TIMEOUT_SECONDS,
        follow_redirects=True,
        verify=_jejunu_ssl_context(),
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("error"):
        raise RuntimeError(f"제주대학교 통합검색 오류: {payload.get('errorMsg') if isinstance(payload, dict) else ''}")
    return payload


def _choose_menu(menus: list[dict[str, Any]], writer: str) -> dict[str, Any] | None:
    usable = [menu for menu in menus if menu.get("CS_URL") and menu.get("URLS")]
    if not usable:
        return None
    if writer:
        writer_match = next(
            (
                menu
                for menu in usable
                if writer in str(menu.get("CS_TITLE") or "")
                and (
                    "공지" in str(menu.get("CM_NAME") or "")
                    or "notice" in str(menu.get("URLS") or "").lower()
                )
            ),
            None,
        )
        if writer_match:
            return writer_match
    return next(
        (
            menu
            for menu in usable
            if menu.get("CS_URL") == "/" and menu.get("CS_TITLE") == "제주대학교"
        ),
        next(
            (
                menu
                for menu in usable
                if "공지" in str(menu.get("CM_NAME") or "")
                or "notice" in str(menu.get("URLS") or "").lower()
            ),
            usable[0],
        ),
    )


def _article_url(menu: dict[str, Any] | None, sequence: int) -> str:
    if not menu:
        return f"{OFFICIAL_SITE_URL}/search/?{urlencode({'q': str(sequence)})}"
    site_path = str(menu["CS_URL"]).rstrip("/")
    menu_path = str(menu["URLS"]).lstrip("/")
    base_url = OFFICIAL_SITE_URL if site_path in ("", "/") else CMS_SITE_URL
    path = f"{site_path}/{menu_path}.htm"
    return f"{base_url}{path}?act=view&seq={sequence}"


def _document_from_detail(item: dict[str, Any], detail: dict[str, Any]) -> JejunuOfficialDocument | None:
    article = detail.get("article")
    if not isinstance(article, dict) or article.get("stat") not in (None, "OK"):
        return None

    sequence = int(article.get("seq") or item.get("BA_SEQ") or 0)
    if sequence <= 0:
        return None
    writer = str(article.get("writer") or item.get("BA_WRITER") or "")
    menus = detail.get("menus") if isinstance(detail.get("menus"), list) else []
    menu = _choose_menu([value for value in menus if isinstance(value, dict)], writer)
    url = _article_url(menu, sequence)
    title = str(article.get("title") or item.get("BA_TITLE") or "제주대학교 공식 공지").strip()
    contents = html_to_text(str(article.get("contents") or ""))
    if not contents:
        contents = html.unescape(str(item.get("BA_CONTENTS") or "")).strip()

    files = detail.get("files") if isinstance(detail.get("files"), list) else []
    attachment_lines = []
    for file_info in files:
        if not isinstance(file_info, dict) or not file_info.get("name"):
            continue
        file_number = file_info.get("no")
        attachment_url = f"{url.split('?')[0]}?act=download&seq={sequence}&no={file_number}"
        attachment_lines.append(f"- {file_info['name']}: {attachment_url}")

    metadata = [
        f"작성일: {item.get('BA_WRITE_TIME') or ''}",
        f"작성자: {writer}",
        f"게시판: {article.get('boardName') or item.get('BB_NAME') or ''}",
    ]
    if attachment_lines:
        metadata.extend(["첨부파일:", *attachment_lines])
    body = "\n".join([*metadata, "", contents]).strip()[:16000]
    return {
        "source_id": f"portal-article-{sequence}",
        "title": title,
        "body": body,
        "url": url,
    }


def fetch_jejunu_official_documents(
    search_query: str,
    *,
    limit: int = DEFAULT_RESULT_LIMIT,
) -> tuple[JejunuOfficialDocument, ...]:
    normalized = search_query.strip()
    if not normalized:
        return ()

    search_payload = _request_json({"q": normalized, "type": SEARCH_TYPE_ALL, "page": 1})
    article_result = search_payload.get("article")
    items = article_result.get("items") if isinstance(article_result, dict) else []
    documents: list[JejunuOfficialDocument] = []
    seen_sequences: set[int] = set()
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        sequence = int(item.get("BA_SEQ") or 0)
        if sequence <= 0 or sequence in seen_sequences:
            continue
        seen_sequences.add(sequence)
        detail = _request_json({"mode": "article", "seq": sequence})
        document = _document_from_detail(item, detail)
        if document:
            documents.append(document)
        if len(documents) >= max(1, min(limit, 5)):
            break
    return tuple(documents)


@lru_cache(maxsize=256)
def search_and_ingest_jejunu_official(search_query: str) -> int:
    """프로세스 안에서는 같은 검색어를 한 번만 조회하고 결과를 공식 RAG에 넣는다."""
    documents = fetch_jejunu_official_documents(search_query)
    if not documents:
        return 0
    return seed_jejunu_official_documents(documents)
