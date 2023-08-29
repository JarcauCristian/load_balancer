import io
import re
from multiprocessing.pool import ThreadPool
import subprocess
import json
import os

import fastapi
import requests
from minio import Minio
from minio.commonconfig import Tags
from typing import List, Dict, Any


class MinIO:

    def __init__(self, sites: Dict[str, str]):
        self.aliases = {}
        self.clients = {}
        self.tokens = {}
        self.current_index = 1

        for site, token in sites.items():
            client = Minio(f'{site.split(":")[1][2:]}:{site.split(":")[2]}',
                           access_key='super',
                           secret_key='doopersecret'
                           )
            self.clients[site] = client
            self.aliases[site] = f'minio{self.current_index}'
            self.tokens[site] = token

            result = os.system('mc alias set minio{} {} super doopersecret'.format(
                self.current_index, site))
            if result != 0:
                print('An error appeared when trying to set the alias for {}, retrying...'.format(site))

            self.current_index += 1

    def add_instances(self, sites: Dict[str, str]) -> bool:
        for site, token in sites.items():
            client = Minio(f'{site.split(":")[1][2:]}:{site.split(":")[2]}',
                           access_key='super',
                           secret_key='doopersecret'
                           )
            self.clients[site] = client
            self.aliases[site] = f'minio{self.current_index}'
            self.tokens[site] = token
            result = os.system('mc alias set minio{} {} super doopersecret'.format(
                self.current_index, site))
            if result != 0:
                print('An error appeared when trying to set the alias for {}, retrying...'.format(site))

            self.current_index += 1

        return True

    def __health(self) -> Dict[str, str]:
        healthy = {}

        pool = ThreadPool(processes=10)

        async_results = []
        for site, alias in self.aliases.items():
            async_result = pool.apply_async(self.__get_health, (alias, site))
            async_results.append(async_result)

        for async_result in async_results:
            status, site, alias = async_result.get()
            if status == "success":
                healthy[site] = alias

        return healthy

    def search_by_tags(self, tags: Dict[str, str]) -> List[Dict[str, List[str]]]:
        healthy = self.__health()

        find_tags = [f' --tags="{k}={v}" ' for k, v in tags.items()]

        pool = ThreadPool(processes=10)

        async_results = []
        for k, v in healthy.items():
            async_result = pool.apply_async(self.__search, ((k, v), find_tags))
            async_results.append(async_result)

        found = []
        for async_result in async_results:
            results = async_result.get()
            if results is not None:
                found.append(results)

        pool.close()
        pool.join()

        return found

    def put_object(self, file: fastapi.UploadFile, tags: Dict[str, str]):
        healthy = self.__health()
        file_size = file.size

        pool = ThreadPool(processes=10)

        async_results = []
        for k, v in healthy.items():
            async_result = pool.apply_async(self.__get_total_bytes, ((k, v), file_size))
            async_results.append(async_result)

        found = []
        for async_result in async_results:
            results = async_result.get()
            if results is not None:
                found.append(results)

        max_dict = max(found, key=lambda d: max(d.values()))

        max_key = max(max_dict, key=max_dict.get)

        client = self.clients[max_key]

        object_tags = self.__create_tags(tags)

        result = client.put_object(
            'dataspace',
            file.filename,
            io.BytesIO(file.file.read()),
            -1, file.content_type,
            part_size=1024*1024*5,
            tags=object_tags
        )

        pool.close()
        pool.join()

        if result is not None:
            return result.bucket_name + '/' + result.object_name, max_key

    @staticmethod
    def __search(health: tuple, tags) -> Dict[Any, List[str]]:
        search_string = f'mc find {health[1]} {"".join(tags)}'
        data = subprocess.check_output(search_string, shell=True).decode('utf-8').split('\n')[:-1]
        return None if len(data) == 0 else {health[0]: data}

    def __get_total_bytes(self, health, file_size):
        token = self.tokens[health[0]]

        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(
            f'https://{health[1]}.sedimark.work:9000/minio/v2/metrics/cluster',
            headers=headers)

        if response.status_code == 200:
            text = response.content.decode('utf-8')
            index = text.find('minio_cluster_capacity_raw_free_bytes{server="127.0.0.1:9000"}')
            pattern = r'[0-9.e+]+'
            matches = re.findall(pattern, text[index + 62:index + 80])
            result = ''.join(matches)
            total_size = float(result)
            return {health[0]: total_size - file_size}

    @staticmethod
    def __create_tags(tags: Dict[str, str]) -> Tags:
        minio_tags = Tags(for_object=True)
        for k, v in tags.items():
            minio_tags[k] = v

        return minio_tags

    @staticmethod
    def __get_health(alias: str, site: str) -> (str, str, str):
        data = json.loads(subprocess.check_output(
            'mc ping {} --count 1 --json'.format(alias), shell=True).decode('utf-8'))
        return data['status'], site, alias
