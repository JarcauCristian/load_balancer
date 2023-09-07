import json
import platform
from typing import Annotated, Optional

import requests
import os
import uvicorn
from tqdm import tqdm
from fastapi import FastAPI, status, UploadFile, Form, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from load_balancer import MinIO
from models import Servers, Tags, Instance, Extension, ContentType, DatasetSearcher, Dataset, Metadata

tags_metadata = [
    {
        "name": "add_instances",
        "description": "This methode is used to add more instances of Minio to the load balancer. The "
                       "methode receives, as a body, a dictionary of Minio servers URLs and the token for "
                       "the Prometheus metrics page."
    },
    {
        "name": "add_instance",
        "description": "This methode is used to add more instances of Minio to the load balancer. The "
                       "methode receives, as a body, the URL for the Minio instance and the token for "
                       "the Prometheus metrics page."
    },
    {
        "name": "search_by_tags",
        "description": "This methode allows the user the search all the Minio instances based on some specified tags. "
                       "This methode receives a dictionary, where the key is the Minio instance and the value is a list"
                       " of the paths to the files that were found."
    },
    {
        "name": "search_by_extension",
        "description": "This methode allows the user the search all the Minio instances based on file extension. "
                       "This methode receives a dictionary, where the key is the Minio instance and the value is a list"
                       " of the paths to the files that were found."
    },
    {
        "name": "search_by_content_type",
        "description": "This methode allows the user the search all the Minio instances based on content type. "
                       "This methode receives a dictionary, where the key is the Minio instance and the value is a list"
                       " of the paths to the files that were found."
    },
    {
        "name": "get_all_objects",
        "description": "This methode allows the user to get all the objects from all instances "
                       "This methode receives a dictionary, where the key is the Minio instance and the value is a list"
                       " of the paths to the files that were found."
    },
    {
        "name": "put_object",
        "description": "This methode allows the user to upload objects to a Minio instance based on the space available"
                       ". This methode receives the file to be uploaded to storage, and the tags related to that file."
    },
    {
        "name": "upload_object",
        "description": "This methode allows the user to upload files to a Minio instance based on the space available"
                       ". This methode receives the file to be uploaded to storage, and the tags related to that file."
    },
     {
        "name": "get_dataset",
        "description": "This methode allows the user to get a shared link to download the required file."
                       ". This methode receives the db client url and the dataset name."
    },
    {
        "name": "get_all_objects_with_details",
        "description": "This methode allows the user to get all the datasets and their corresponding metadata and tags."
                       ". This methode doesn't receive any data."
    }
]

app = FastAPI(openapi_tags=tags_metadata)

origins = [
    "http://localhost.tiangolo.com",
    "https://localhost.tiangolo.com",
    "http://localhost",
    "http://localhost:3001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

minio_instance = None


def init():
    operating_system = platform.system()
    if operating_system == 'Windows':
        if not os.path.exists('mc.exe'):
            buffer_size = 1024
            url = 'https://dl.min.io/client/mc/release/windows-amd64/mc.exe'
            response = requests.get(url, stream=True)
            file_size = int(response.headers.get("Content-Length", 0))
            default_filename = url.split("/")[-1]

            progress = tqdm(response.iter_content(buffer_size), f"Downloading {default_filename}",
                            total=file_size, unit="B",
                            unit_scale=True, unit_divisor=1024)
            with open(default_filename, "wb") as f:
                for data in progress.iterable:
                    f.write(data)
                    progress.update(len(data))
    elif operating_system == 'Linux':
        if not os.path.exists('$HOME/minio-binaries/mc'):
            result = os.system('curl https://dl.min.io/client/mc/release/linux-amd64/mc --create-dirs '
                               '-o $HOME/minio-binaries/mc')
            if result == 0:
                os.system('chmod +x $HOME/minio-binaries/mc')


@app.post("/add_instances", status_code=201, tags=["add_instances"])
async def add_instances(servers: Servers):
    if len(servers.servers) > 0:
        global minio_instance
        if isinstance(minio_instance, MinIO):
            result = minio_instance.add_instances(servers.servers)
            if len(result) == 0:
                return {"message": "Added instances successfully!"}
            else:
                message = ", ".join(result)
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content=f'Error adding instances: {message}'
                )
        else:
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content='The Minio instance was not created.')
    else:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content="Servers could not be empty")


@app.post("/add_instance", status_code=201, tags=["add_instance"])
async def add_instance(instance: Instance):
    if len(instance.url) > 0 and len(instance.token) > 0:
        global minio_instance
        if isinstance(minio_instance, MinIO):
            result = minio_instance.add_instances([{
                'url': instance.url,
                'token': instance.token,
                'access_key': instance.access_key,
                'secret_key': instance.secret_key
            }])
            if len(result) == 0:
                return {"message": "Added instance successfully!"}
            else:
                return JSONResponse(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    content='Error when trying to add the instance'
                )
        else:
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content='The Minio instance was not created.')
    else:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content="Servers could not be empty")


@app.post("/search_by_tags", status_code=200, tags=["search_by_tags"])
async def search_by_tags(tags: Tags):
    global minio_instance
    if isinstance(minio_instance, MinIO):
        return minio_instance.search_by_tags(tags.tags)
    else:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content='The Minio instance was not created.'
        )


@app.post("/search_by_extension", tags=["search_by_extension"])
async def search_by_extension(extension: Extension):
    global minio_instance
    if isinstance(minio_instance, MinIO):
        return minio_instance.search_by_file_extension(extension.extension)
    else:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content='The Minio instance was not created.'
        )


@app.post("/search_by_content_type", tags=["search_by_content_type"])
async def search_by_content_type(content_type: ContentType):
    global minio_instance
    if isinstance(minio_instance, MinIO):
        return minio_instance.search_by_content_type(content_type.content_type)
    else:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content='The Minio instance was not created.'
        )


@app.get("/get_all_objects", tags=["get_all_objects"])
async def get_all_objects():
    global minio_instance
    if isinstance(minio_instance, MinIO):
        return minio_instance.get_all_objects()
    else:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content='The Minio instance was not created.'
        )

@app.get("/get_all_objects_with_details", tags=["get_all_objects_with_details"])
async def get_all_objects():
    global minio_instance
    if isinstance(minio_instance, MinIO):
        datasets_with_details = []
        datasets = minio_instance.get_all_objects()
        for entry in datasets:
            for key in entry:
                for dataset in entry[key]:
                    if "/" in dataset:
                        if "jsonld" in dataset.lower():
                            metadata = minio_instance.get_dataset_metadata(key, dataset)
                            tags     = minio_instance.get_dataset_tags(key, dataset)
                            if metadata != "failed" and tags != "failed":
                                dataset_with_details = {
                                    "name": dataset.split("/")[-1],
                                    "metadata": {
                                        "MetaAccess": metadata[
                                            'X-Amz-Meta-Access'] if 'X-Amz-Meta-Access' in metadata else None,
                                        "MetaDownload": metadata[
                                            'X-Amz-Meta-Download'] if 'X-Amz-Meta-Download' in metadata else None,
                                        "MetaUploadDate": metadata[
                                            'X-Amz-Meta-Uploaddate'] if 'X-Amz-Meta-Uploaddate' in metadata else None,
                                        "MetaTagCount":metadata[
                                        'X-Amz-Tagging-Count'] if 'X-Amz-Tagging-Count' in metadata else None,
                                        "Source": key
                                    },
                                    "tags": tags
                                }
                                datasets_with_details.append(dataset_with_details)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=datasets_with_details
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content='The Minio instance was not created.'
        )


@app.post("/get_dataset", tags=["get_dataset"])
async def get_dataset(dataset_searcher: DatasetSearcher):
    global minio_instance
    if isinstance(minio_instance, MinIO):
        dataset_link = minio_instance.get_dataset(dataset_searcher.url, dataset_searcher.name)
        if dataset_link == "failed":
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content='The dataset was not found.'
            )
        else:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={"dataset": dataset_link}
            )
    else:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content='First create the dataset at /put_object/'
        )


@app.put("/put_object", status_code=201, tags=["put_object"])
async def put_object(file: Annotated[bytes, File()], file_name: Annotated[str, Form()],
                     tags: Optional[str] = Form(None)):
    global minio_instance
    file_size = len(file)
    tags = json.loads(tags) if tags is not None else json.loads('{}')
    if isinstance(minio_instance, MinIO):
        result, site = minio_instance.put_object((file, file_name), file_size, tags)
        if result is not None and site is not None:
            return {f"Uploaded file {file} to {result} on client {site}"}
        else:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content='There was no place where to put the object'
            )
    else:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED, content='The Minio instance was not created.'
        )


@app.put("/upload_object", status_code=201, tags=["upload_object"])
async def upload_object(file: UploadFile, tags: Optional[str] = Form(None)):
    global minio_instance
    tags = json.loads(tags) if tags is not None else json.loads('{}')
    if isinstance(minio_instance, MinIO):
        result, site = minio_instance.upload_object(file, tags)
        if result is not None and site is not None:
            return {f"Uploaded file {file} to {result} on client {site}"}
        else:
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content='There was no place where to put the object'
            )
    else:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED, content='The Minio instance was not created.'
        )


if __name__ == '__main__':
    init()

    minio_instance = MinIO()

    uvicorn.run(app, host="0.0.0.0", port=8001)
