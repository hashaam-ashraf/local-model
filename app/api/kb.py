from fastapi import APIRouter, Depends

from app.config import Project, Settings
from app.core.dependencies import get_llm, get_project, get_settings, get_store, require_admin
from app.schemas.kb import IndexResponse
from app.services.kb_service import rebuild_index
from app.services.llm_service import LLM
from app.services.store_service import Store

router = APIRouter(tags=["knowledge base"])


@router.post("/{slug}/index", response_model=IndexResponse, dependencies=[Depends(require_admin)])
def index(
    project: Project = Depends(get_project),
    settings: Settings = Depends(get_settings),
    llm: LLM = Depends(get_llm),
    store: Store = Depends(get_store),
):
    return {"project": project.slug, "sections": rebuild_index(settings, llm, store, project)}
