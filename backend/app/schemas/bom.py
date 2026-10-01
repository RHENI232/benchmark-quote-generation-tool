from pydantic import BaseModel

class BOMLineSpec(BaseModel):
    lookup_key: str
    quantity: int
    section: str
