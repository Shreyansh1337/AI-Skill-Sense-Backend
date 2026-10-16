
from pydantic import BaseModel, HttpUrl


class URLProcessRequest(BaseModel):
    url: HttpUrl

class URLProcessResponse(BaseModel):
    url: str

class URLGetIDRequest(BaseModel):
    url: HttpUrl

class URLGetIDResponse(BaseModel):
    url_id: str
