from pydantic import BaseModel


class KakaoIngestResponse(BaseModel):
    ingested: int
    cursor: int


class PartyCleanupResponse(BaseModel):
    deleted: int
