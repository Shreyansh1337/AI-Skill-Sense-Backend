
from fastapi import APIRouter
from schemas.url import (
    URLGetIDRequest,
    URLGetIDResponse,
    URLProcessRequest,
    URLProcessResponse,
)

router = APIRouter(
    prefix="/api/urls",
    tags=["URLs"],
)

@router.post("/process", response_model=URLProcessResponse)
def process_url(request: URLProcessRequest):
    return {"url": str(request.url)}

@router.post("/get-id", response_model=URLGetIDResponse)
def get_url_id(request: URLGetIDRequest):
    raise NotImplementedError("URL ID lookup is not implemented yet.")