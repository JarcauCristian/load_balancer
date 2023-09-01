from pydantic import BaseModel
from typing import Dict, List


class Instance(BaseModel):
    url: str
    token: str
    access_key: str
    secret_key: str


class Servers(BaseModel):
    servers: List[Dict[str, str]]


class Tags(BaseModel):
    tags: Dict[str, str]


class Extension(BaseModel):
    extension: str


class ContentType(BaseModel):
    content_type: str
