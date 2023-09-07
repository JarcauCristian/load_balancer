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

class DatasetSearcher(BaseModel):
    url: str
    name: str


class Dataset(BaseModel):
    name: str
    tags: dict | None = {}
    metadata: dict | None = {}


class Metadata(BaseModel):
    MetaAccess: str | None = ""
    MetaDownload: str | None = ""
    MetaUploadDate: str | None = ""
    MetaTagCount: str | None =
