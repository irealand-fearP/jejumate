"""
카카오톡 오픈채팅 txt 내보내기 파서 + 대화 단위 청킹.

내보내기 형식: `[닉네임] [오후 2:11] 내용`.
- 메시지 본문은 여러 줄로 이어질 수 있다(다음 `[닉네임] [시간]` 줄이 나오기 전까지
  이어지는 모든 줄은 이전 메시지의 연속으로 본다).
- 입장/퇴장/삭제/공지봇 등은 실제 대화가 아닌 노이즈라 걸러낸다.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

_DATE_SEPARATOR_RE = re.compile(r"^-+\s*(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일")
_MESSAGE_RE = re.compile(
    r"^\[(?P<nickname>.+?)\]\s*\[(?P<ampm>오전|오후)\s*(?P<hour>\d{1,2}):(?P<minute>\d{2})\]\s*(?P<content>.*)$"
)

# 실제 유저 발화가 아닌 시스템 발신자
_BOT_NICKNAMES = {"오픈채팅봇"}

# 카톡 내보내기 파일에 섞여 들어오는 제어문자(예: 백스페이스 0x08) 제거용.
# 같은 사람 닉네임이 제어문자 유무로 다르게 파싱되는 걸 막는다.
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

# 대화 내용이 아닌 시스템 안내/이벤트 줄로 간주할 패턴(부분 일치)
_NOISE_SUBSTRINGS = (
    "님이 들어왔습니다",
    "님이 나갔습니다",
    "메시지가 삭제되었습니다",
    "타인, 기관 등의 사칭에 유의",
    "불법촬영물 식별 및 게재제한 안내",
    "전기통신사업법에 따라",
)


@dataclass
class ParsedMessage:
    nickname: str
    timestamp: datetime
    content: str


@dataclass
class ConversationChunk:
    nickname: str
    start_timestamp: datetime
    end_timestamp: datetime
    content: str
    message_count: int = 1


def _is_header_line(line: str) -> bool:
    return line.endswith("카카오톡 대화") or line.startswith("저장한 날짜")


def _is_noise_line(line: str) -> bool:
    if _is_header_line(line):
        return True
    return any(marker in line for marker in _NOISE_SUBSTRINGS)


def _to_24h(ampm: str, hour: int) -> int:
    if ampm == "오전":
        return 0 if hour == 12 else hour
    return 12 if hour == 12 else hour + 12


def parse_kakao_txt(text: str) -> list[ParsedMessage]:
    """카카오톡 내보내기 텍스트를 파싱해 노이즈를 제거한 메시지 리스트를 반환한다."""
    messages: list[ParsedMessage] = []
    current: dict | None = None
    current_date: tuple[int, int, int] | None = None

    def finalize():
        nonlocal current
        if current is not None:
            content = "\n".join(current["lines"]).strip()
            if content:
                messages.append(
                    ParsedMessage(current["nickname"], current["timestamp"], content)
                )
            current = None

    for raw_line in text.splitlines():
        line = _CONTROL_CHAR_RE.sub("", raw_line.rstrip("\n"))

        date_match = _DATE_SEPARATOR_RE.match(line.strip())
        if date_match:
            finalize()
            year, month, day = (int(g) for g in date_match.groups())
            current_date = (year, month, day)
            continue

        stripped = line.strip()
        if _is_noise_line(stripped):
            finalize()
            continue

        message_match = _MESSAGE_RE.match(line)
        if message_match:
            finalize()
            nickname = message_match.group("nickname")
            if nickname in _BOT_NICKNAMES:
                continue

            hour = _to_24h(message_match.group("ampm"), int(message_match.group("hour")))
            minute = int(message_match.group("minute"))
            year, month, day = current_date or (1970, 1, 1)
            timestamp = datetime(year, month, day, hour, minute)

            current = {
                "nickname": nickname,
                "timestamp": timestamp,
                "lines": [message_match.group("content")],
            }
            continue

        # 이전 메시지의 연속(멀티라인 본문). 대화가 시작되기 전 줄(빈 줄 등)은 버린다.
        if current is not None:
            current["lines"].append(line)

    finalize()
    return messages


def chunk_messages(
    messages: list[ParsedMessage], max_gap: timedelta = timedelta(minutes=5)
) -> list[ConversationChunk]:
    """같은 화자가 max_gap 이내로 연속 발화한 메시지를 하나의 대화 단위로 묶는다."""
    chunks: list[ConversationChunk] = []
    current: ConversationChunk | None = None

    for message in messages:
        if (
            current is not None
            and current.nickname == message.nickname
            and message.timestamp - current.end_timestamp <= max_gap
        ):
            current.content += "\n" + message.content
            current.end_timestamp = message.timestamp
            current.message_count += 1
        else:
            if current is not None:
                chunks.append(current)
            current = ConversationChunk(
                nickname=message.nickname,
                start_timestamp=message.timestamp,
                end_timestamp=message.timestamp,
                content=message.content,
            )

    if current is not None:
        chunks.append(current)

    return chunks
