import io
import re
from multiprocessing.pool import ThreadPool
import subprocess
import json
import os
import base64

import fastapi
import requests
from minio import Minio
from minio.commonconfig import Tags
from typing import List, Dict, Any


class MinIO:

    def __init__(self):
        self.aliases = {}
        self.clients = {}
        self.tokens = {}
        self.current_index = 1

        with open('./configs/config.json', 'r') as json_in:
            config: List[Dict[str, str]] = json.loads(json_in.read())

        self.current_index = int(config[-1]['alias'].split('o')[-1]) + 1

        for instance in config:
            access_key = base64.b64decode(instance['access_key'].encode('utf-8')).decode('utf-8')
            secret_key = base64.b64decode(instance['secret_key'].encode('utf-8')).decode('utf-8')
            client = Minio(f'{instance["site"].split(":")[1][2:]}:{instance["site"].split(":")[2]}',
                           access_key=access_key,
                           secret_key=secret_key
                           )
            self.clients[instance['site']] = client
            self.aliases[instance['site']] = instance['alias']
            self.tokens[instance['site']] = instance['token']

            result = os.system('mc alias set minio{} {} {} {}'.format(
                instance['alias'].split('o')[-1], instance['site'], access_key, secret_key))

            if result == 0:
                print('Added successfully!')

    def add_instances(self, sites: List[Dict[str, str]]) -> List[str]:
        with open('./configs/config.json', 'r') as json_in:
            config: List[Dict[str, str]] = json.loads(json_in.read())

        errors = []
        for site in sites:
            client = Minio(f'{site["url"].split(":")[1][2:]}:{site["url"].split(":")[2]}',
                           access_key=site['access_key'],
                           secret_key=site['secret_key']
                           )
            self.clients[site['url']] = client
            self.aliases[site['url']] = f'minio{self.current_index}'
            self.tokens[site['url']] = site['token']
            instance = {
                'site': site['url'],
                'token': site['token'],
                'alias': f'minio{self.current_index}',
                'access_key': base64.b64encode(site['access_key'].encode('utf-8')).decode('utf-8'),
                'secret_key': base64.b64encode(site['secret_key'].encode('utf-8')).decode('utf-8')
            }
            result = os.system('mc alias set minio{} {} {} {}'.format(
                self.current_index, site['url'], site['access_key'], site['secret_key']))
            if result != 0:
                errors.append(site['url'])
            else:
                config.append(instance)

            self.current_index += 1

        with open('./configs/config.json', 'w') as json_out:
            json_out.write(json.dumps(config, indent=4))

        return errors

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

        pool.close()
        pool.join()

        return healthy

    def search_by_tags(self, tags: Dict[str, str]) -> List[Dict[str, List[str]]]:
        healthy = self.__health()

        find_tags = [f' --tags="{k}={v}" ' for k, v in tags.items()]

        pool = ThreadPool(processes=10)

        async_results = []
        for k, v in healthy.items():
            async_result = pool.apply_async(self.__search_tags, ((k, v), find_tags))
            async_results.append(async_result)

        found = []
        for async_result in async_results:
            results = async_result.get()
            if results is not None:
                found.append(results)

        pool.close()
        pool.join()

        return found

    def search_by_file_extension(self, extension: str) -> List[Dict[str, List[str]]]:
        healthy = self.__health()

        find_extension = f' --name="*.{extension}" '

        pool = ThreadPool(processes=10)

        async_results = []
        for k, v in healthy.items():
            async_result = pool.apply_async(self.__search_extension, ((k, v), find_extension))
            async_results.append(async_result)

        found = []
        for async_result in async_results:
            results = async_result.get()
            if results is not None:
                found.append(results)

        pool.close()
        pool.join()

        return found

    def search_by_content_type(self, content_type: str) -> List[Dict[str, List[str]]]:
        healthy = self.__health()

        find_content_type = f' --metadata="content-type={content_type}" '

        pool = ThreadPool(processes=10)

        async_results = []
        for k, v in healthy.items():
            async_result = pool.apply_async(self.__search_content_type, ((k, v), find_content_type))
            async_results.append(async_result)

        found = []
        for async_result in async_results:
            results = async_result.get()
            if results is not None:
                found.append(results)

        pool.close()
        pool.join()

        return found

    def get_all_objects(self) -> List[Dict[str, List[str]]]:
        healthy = self.__health()

        pool = ThreadPool(processes=10)

        async_results = []
        for k, v in healthy.items():
            async_result = pool.apply_async(self.__get_all, (k, v))
            async_results.append(async_result)

        found = []
        for async_result in async_results:
            results = async_result.get()
            if results is not None:
                found.append(results)

        pool.close()
        pool.join()

        return found

    def put_object(self, file: (bytes, str), file_size: int, tags: Dict[str, str]) -> (str, str):
        healthy = self.__health()

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
            file[1],
            io.BytesIO(file[0]),
            -1,
            'application/json',
            part_size=1024*1024*5,
            tags=object_tags
        )

        pool.close()
        pool.join()

        if result is not None:
            return result.bucket_name + '/' + result.object_name, max_key

    def upload_object(self, file: fastapi.UploadFile, tags: Dict[str, str]) -> (str, str):
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
    def __search_tags(health: tuple, tags: Dict[str, str]) -> Dict[Any, List[str]] | None:
        search_string = f'mc find {health[1]} {"".join(tags)}'
        data = subprocess.check_output(search_string, shell=True).decode('utf-8').split('\n')[:-1]
        data = ["/".join(d.split('/')[1:]) for d in data]
        return None if len(data) == 0 else {health[0]: data}

    @staticmethod
    def __search_extension(health: tuple, extension: str) -> Dict[Any, List[str]] | None:
        search_string = f'mc find {health[1]} {extension}'
        data = subprocess.check_output(search_string, shell=True).decode('utf-8').split('\n')[:-1]
        data = ["/".join(d.split('/')[1:]) for d in data]
        return None if len(data) == 0 else {health[0]: data}

    @staticmethod
    def __search_content_type(health: tuple, content_type: str) -> Dict[Any, List[str]] | None:
        search_string = f'mc find {health[1]} {content_type}'
        data = subprocess.check_output(search_string, shell=True).decode('utf-8').split('\n')[:-1]
        data = ["/".join(d.split('/')[1:]) for d in data]
        return None if len(data) == 0 else {health[0]: data}

    @staticmethod
    def __get_all(site: str, alias: str) -> Dict[Any, List[str]] | None:
        search_string = f'mc find {alias} '
        data = subprocess.check_output(search_string, shell=True).decode('utf-8').split('\n')[:-1]
        data = ["/".join(d.split('/')[1:]) for d in data]
        return None if len(data) == 0 else {site: data}

    def __get_total_bytes(self, health: (str, str), file_size: int) -> Dict[str, float]:
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
        else:
            return {health[0]: 0}

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
