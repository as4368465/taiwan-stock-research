"""公開的投資術語小百科查詢 API。"""

from typing import Annotated

from fastapi import APIRouter, Query

from app.schemas.glossary import GlossaryCategory, GlossaryResponse
from app.services.glossary_service import search_glossary

router = APIRouter(prefix="/glossary", tags=["glossary"])


@router.get("", response_model=GlossaryResponse)
def get_glossary(
    q: Annotated[str | None, Query(max_length=80)] = None,
    category: GlossaryCategory | None = None,
) -> GlossaryResponse:
    return search_glossary(q, category)
