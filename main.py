import json
import platform
from typing import Annotated, Optional

import requests
import os
import uvicorn
from tqdm import tqdm
from fastapi import FastAPI, status, UploadFile, Form, File
from fastapi.responses import JSONResponse
from load_balancer import MinIO
from models import Servers, Tags, Instance

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
                       "The methode receives a dictionary of tags with the key being the tag, and the value, the value "
                       "of the tag."
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
    }
]

app = FastAPI(openapi_tags=tags_metadata)

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


@app.post("/add_instances/", status_code=201, tags=["add_instances"])
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
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content='First create the instance '
                                                                                  'at /create_instance/')
    else:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content="Servers could not be empty")


@app.post("/add_instance/", status_code=201, tags=["add_instance"])
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
            return JSONResponse(status_code=status.HTTP_401_UNAUTHORIZED, content='First create the instance '
                                                                                  'at /create_instance/')
    else:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content="Servers could not be empty")


@app.post("/search_by_tags/", tags=["search_by_tags"])
async def search_by_tags(tags: Tags):
    global minio_instance
    if isinstance(minio_instance, MinIO):
        return minio_instance.search_by_tags(tags.tags)
    else:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content='First create the instance at /create_instance/'
        )


@app.put("/put_object/", status_code=201, tags=["put_object"])
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
            status_code=status.HTTP_401_UNAUTHORIZED, content='First create the instance at /create_instance/'
        )


@app.put("/upload_object/", status_code=201, tags=["upload_object"])
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
            status_code=status.HTTP_401_UNAUTHORIZED, content='First create the instance at /create_instance/'
        )


if __name__ == '__main__':
    init()

    minio_instance = MinIO()

    uvicorn.run(app, host="0.0.0.0", port=8000)
