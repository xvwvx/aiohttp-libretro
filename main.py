import asyncio
import json
import os.path
import shutil
import time
import urllib
import zipfile

import aiohttp

target_url = "http://buildbot.libretro.com/nightly/android/latest/arm64-v8a/"
out_path = "./download"


async def fetch(session, url, data=None):
    async with session.post(url, data=data) if not data is None else session.get(url) as response:
        return await response.text()


async def download_file(session, url, file_path):
    async with session.get(url, timeout=None) as r:
        path = os.path.dirname(file_path)
        os.makedirs(path, exist_ok=True)

        size = 1024 * 8
        with open(file_path, 'wb') as file:
            start = time.time()
            count = 0
            while True:
                chunk = await r.content.read(size)
                if not chunk:
                    break
                count += 1
                diff = time.time() - start
                if count % 10 == 0:
                    print(f'{diff:0.2f}s, downloaded: {count * size / (1024 * 1024):0.2f}MB')
                file.write(chunk)


async def main():
    connector = aiohttp.TCPConnector(ssl=False)  # 防止ssl报错
    async with aiohttp.ClientSession(connector=connector) as session:
        parsed_uri = urllib.parse.urlparse(target_url)
        data = {
            "action": "get",
            "items": {
                "href": parsed_uri.path,
                "what": 1
            }
        }
        content = await fetch(session, target_url, json.dumps(data))
        result = json.loads(content)
        items = result["items"]

        suffix_map = {
            "windows": ".dll.zip",
            "linux": ".so.zip",
            "nintendo": ".nro.zip",
            "android": ".so.zip",
            "apple/osx": ".dylib.zip",
            "apple/ios": ".dylib.zip",
        }

        key = next(v for v in suffix_map.keys() if target_url.__contains__(v))
        suffix = suffix_map[key]
        items = map(lambda v: v["href"], items)
        items = filter(lambda v: v.endswith(suffix), items)
        items = list(items)

        local_base_url = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)

        tmp_path = "./tmp"
        for item in items:
            url = urllib.parse.urljoin(local_base_url, item)
            await download_file(session, url, os.path.join(tmp_path, os.path.basename(item)))

        file_names = [f for f in os.listdir(tmp_path) if
                      os.path.isfile(os.path.join(tmp_path, f)) and f.endswith(suffix)]

        for name in file_names:
            os.makedirs(out_path, exist_ok=True)
            with zipfile.ZipFile(os.path.join(tmp_path, name), "r") as zip_file:
                # path = os.path.join(out_path, os.path.splitext(name)[0])
                namelist = zip_file.namelist()

                for f in namelist:
                    zip_file.extract(f, out_path)

        try:
            shutil.rmtree(tmp_path)
        except OSError as e:
            print("Error: %s - %s." % (e.filename, e.strerror))


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
