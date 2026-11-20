from pydantic import BaseModel


class ProjectResponse(BaseModel):
    slug: str
    name: str
    models: list[str]  # the default first
