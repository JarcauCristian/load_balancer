from pydantic import BaseModel
from typing import Dict


class Servers(BaseModel):
    servers: Dict[str, str]


class Tags(BaseModel):
    tags: Dict[str, str]
