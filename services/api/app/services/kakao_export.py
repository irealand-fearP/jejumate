"""카카오톡 PC 대화 내보내기 파일 파싱과 중간 수집 서버 업로드 도구."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.request import Request, urlopen


_ROOM_PATTERN = re.compile(r"^(?P<room>.+?)(?: 님과)? 카카오톡 대화$")
_DATE_PATTERN = re.compile(
    r"^-+ (?P<year>\d{4})년 (?P<month>\d{1,2})월 (?P<day>\d{1,2})일 .+ -+$"
)
_MESSAGE_PATTERN = re.compile(
    r"^\[(?P<sender>[^\]]+)\] \[(?P<meridiem>오전|오후) "
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\] (?P<content>.*)$"
)


@dataclass(frozen=True)
class KakaoExportMessage:
    room: str
    sender: str
    sent_at: datetime
    content: str

    @property
    def sent_at_text(self) -> str:
        return self.sent_at.strftime("%Y-%m-%d %H:%M:00")

    @property
    def client_message_hash(self) -> str:
        # PC 내보내기는 초 단위 시각이나 메시지 ID를 제공하지 않는다. 겹치는 10분
        # 내보내기에서 같은 메시지가 다시 올라가지 않도록 안정적인 필드만 사용한다.
        canonical = "\x1f".join((self.room, self.sender, self.sent_at_text, self.content))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_api_payload(self) -> dict[str, str]:
        return {
            "room": self.room,
            "sender": self.sender,
            "sent_at_text": self.sent_at_text,
            "content": self.content,
            "client_message_hash": self.client_message_hash,
        }


@dataclass(frozen=True)
class KakaoExport:
    room: str
    messages: tuple[KakaoExportMessage, ...]


def _to_24_hour(meridiem: str, hour: int) -> int:
    if meridiem == "오전":
        return 0 if hour == 12 else hour
    return hour if hour == 12 else hour + 12


def parse_kakao_export_text(text: str) -> KakaoExport:
    """카카오톡 PC의 그룹 대화 텍스트 내보내기를 구조화한다.

    날짜 구분선 뒤의 ``[작성자] [오전/오후 시각] 본문``만 메시지로 취급한다.
    첫 메시지 전의 공지·방 안내 문구는 제외하고, 메시지 뒤의 비표준 행은 해당
    메시지의 여러 줄 본문으로 합친다.
    """
    lines = text.splitlines()
    if not lines:
        raise ValueError("빈 카카오톡 내보내기 파일입니다.")

    room_match = _ROOM_PATTERN.fullmatch(lines[0].strip())
    if not room_match:
        raise ValueError("카카오톡 내보내기 헤더에서 채팅방 이름을 찾지 못했습니다.")
    room = room_match.group("room").strip()

    current_date: tuple[int, int, int] | None = None
    messages: list[KakaoExportMessage] = []

    for raw_line in lines[1:]:
        line = raw_line.rstrip()
        date_match = _DATE_PATTERN.fullmatch(line)
        if date_match:
            current_date = (
                int(date_match.group("year")),
                int(date_match.group("month")),
                int(date_match.group("day")),
            )
            continue

        message_match = _MESSAGE_PATTERN.fullmatch(line)
        if message_match and current_date:
            hour = _to_24_hour(
                message_match.group("meridiem"), int(message_match.group("hour"))
            )
            sent_at = datetime(
                *current_date,
                hour,
                int(message_match.group("minute")),
            )
            messages.append(
                KakaoExportMessage(
                    room=room,
                    sender=message_match.group("sender").strip(),
                    sent_at=sent_at,
                    content=message_match.group("content").strip(),
                )
            )
            continue

        # 내보내기 헤더와 첫 메시지 전의 방 공지는 수집하지 않는다. 실제 메시지
        # 이후의 비표준 행은 사용자가 입력한 줄바꿈 본문일 수 있어 이어 붙인다.
        if line and messages:
            previous = messages[-1]
            messages[-1] = KakaoExportMessage(
                room=previous.room,
                sender=previous.sender,
                sent_at=previous.sent_at,
                content=f"{previous.content}\n{line}".strip(),
            )

    return KakaoExport(room=room, messages=tuple(messages))


def parse_kakao_export(path: Path) -> KakaoExport:
    return parse_kakao_export_text(path.read_text(encoding="utf-8-sig"))


def post_chat_messages(
    endpoint: str,
    messages: list[KakaoExportMessage],
    *,
    upload_secret: str,
    timeout_seconds: int = 15,
) -> Any:
    """시냅스팟의 인증된 카카오 메시지 엔드포인트로 일괄 업로드한다."""
    if not upload_secret:
        raise ValueError("카카오 업로드 비밀키가 필요합니다.")
    body = json.dumps(
        {"messages": [message.to_api_payload() for message in messages]},
        ensure_ascii=False,
    ).encode("utf-8")
    request = Request(
        endpoint,
        data=body,
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {upload_secret}",
        },
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - configured API endpoint
        payload = response.read()
    return json.loads(payload) if payload else None


def process_queued_messages(
    endpoint: str,
    *,
    upload_secret: str,
    max_items: int = 1,
    timeout_seconds: int = 60,
) -> Any:
    if not upload_secret:
        raise ValueError("카카오 업로드 비밀키가 필요합니다.")
    separator = "&" if "?" in endpoint else "?"
    request = Request(
        f"{endpoint}{separator}max_items={max_items}",
        data=b"",
        headers={"Authorization": f"Bearer {upload_secret}"},
        method="POST",
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - configured API endpoint
        payload = response.read()
    return json.loads(payload) if payload else None
