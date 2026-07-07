from pydantic import BaseModel


class KakaoIngestResponse(BaseModel):
    ingested: int
    cursor: int
