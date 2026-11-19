from pydantic import BaseModel


class IndexResponse(BaseModel):
    project: str
    sections: int
