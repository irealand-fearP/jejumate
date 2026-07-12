from pydantic import BaseModel, Field


class KakaoIngestResponse(BaseModel):
    ingested: int
    cursor: int


class KakaoUploadMessage(BaseModel):
    room: str = Field(min_length=1, max_length=200)
    sender: str = Field(min_length=1, max_length=100)
    sent_at_text: str = Field(min_length=1, max_length=40)
    content: str = Field(min_length=1, max_length=5000)
    client_message_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class KakaoUploadRequest(BaseModel):
    messages: list[KakaoUploadMessage] = Field(min_length=1, max_length=20)


class KakaoUploadResponse(BaseModel):
    received: int
    accepted: int
    duplicates: int
    pending: int


class KakaoProcessResponse(BaseModel):
    ingested: int
    filtered: int
    pending: int


class PartyCleanupResponse(BaseModel):
    deleted: int
