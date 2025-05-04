"""
 Copyright (c) 2025 qbit529

 This program is free software: you can redistribute it and/or modify
 it under the terms of the GNU General Public License as published by
 the Free Software Foundation, either version 3 of the License, or
 (at your option) any later version.

 This program is distributed in the hope that it will be useful,
 but WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 GNU General Public License for more details.

 You should have received a copy of the GNU General Public License
 along with this program. If not, see <https://www.gnu.org/licenses/>.
 """


import asyncio
import hashlib
import json
import os
import io
from urllib.parse import unquote, urlparse
from ..lib.mangadex_api import get_manga_info, get_volumes_and_chapters, get_chapter_image_urls
from ..lib.utils import download_bytes, ensure_image_vertical, delete_files_older_than
from typing import Dict, Tuple
from calibre.utils.zipfile import ZipFile
from calibre.utils.config import config_dir

parallel_worker_limit = 1
PLUGIN_ID = 'MangaDex'
CACHE_DIR = os.path.join(
    config_dir, 'plugins', PLUGIN_ID, 'cbz_cache')
os.makedirs(CACHE_DIR, exist_ok=True)

tasks_status: Dict[str, Tuple[str, str]] = {}
worker_semaphore = None

def get_worker_semaphore() -> asyncio.Semaphore:
    global worker_semaphore, parallel_worker_limit
    if worker_semaphore != None:
        return worker_semaphore
    else:
        worker_semaphore = asyncio.Semaphore(parallel_worker_limit)
        return worker_semaphore

async def get_chapter_image_urls_with_fallback(
        chapter_id_variants: list[str], page_prefix: str) -> list[(str, str)]:
    image_urls = []
    for chapter_id in chapter_id_variants:
        image_urls = await get_chapter_image_urls(chapter_id)
        if len(image_urls) > 0:
            break
    return [(i, page_prefix) for i in image_urls]


async def prepare_manga_metadata(
        manga_id: str, volume_name: str, lang: str, chapter_names: list[str], part: int, my_zip) -> list[(str, str)]:
    manga_info = await get_manga_info(manga_id)
    volumes = await get_volumes_and_chapters(manga_id, lang)
    volume = next((v for v in volumes if v.name == volume_name))
    chapters = [c for c in volume.chapters if c.name in chapter_names]
    tasks = []
    image_urls = []
    for chapter in chapters:
        padded_chapter_index = f"{volume_name}/{chapter.sort:09.2f}/"
        tasks.append(asyncio.create_task(
            get_chapter_image_urls_with_fallback(
                chapter.chapter_id_variants, padded_chapter_index)))
    for t in tasks:
        image_urls += await t
    my_zip.writestr("ComicInfo.xml",
                    manga_info.to_comic_info_xml(volume_name, lang, part))
    comment_bytes = json.dumps(manga_info.to_comic_book_info_json(
        volume_name, lang, part)).encode("utf-8")
    my_zip.comment = comment_bytes
    return image_urls


def _get_image_filename(url, chapter_prefix, img_index):
    parsed_url = urlparse(url)
    padded_index = f"{img_index + 1:04d}"
    return chapter_prefix + "_" + padded_index + \
        "_" + unquote(os.path.basename(parsed_url.path))


async def download_image_to_zip(image_url: str, chapter_prefix: str, index: int, my_zip):
    file_name = _get_image_filename(image_url, chapter_prefix, index)
    print('downloading', image_url)
    image_data = io.BytesIO(await download_bytes(image_url))
    print('downloading', image_url, 'done')
    rotated_io = ensure_image_vertical(image_data)
    my_zip.writestr(file_name, rotated_io.getvalue())


def get_file_name(prefix: str, volume_name: str, part: int, language: str, manga_id: str):
    return ".".join([prefix, volume_name, str(part), language, manga_id, "cbz"])


async def put_mangadex_volume(
        task_id: str, prefix: str, manga_id: str, language: str,
        volume_name: str, chapter_names: list[str], part: int):
    global CACHE_DIR
    async with get_worker_semaphore():
        tasks_status[task_id] = ("running", "")
        try:
            delete_files_older_than(CACHE_DIR, hours=12)
            zip_file_name = get_file_name(
                prefix, volume_name, part, language, manga_id)
            zip_file_name = task_id + "." + zip_file_name
            zip_file_path = os.path.join(CACHE_DIR, zip_file_name)
            with ZipFile(zip_file_path, mode='w') as my_zip:
                image_urls = await prepare_manga_metadata(
                    manga_id, volume_name, language, chapter_names, part, my_zip)
                total_images = len(image_urls)
                completed = 0
                tasks = [
                    asyncio.create_task(
                        download_image_to_zip(
                            url, prefix, index, my_zip
                        )
                    )
                    for index, (url, prefix) in enumerate(image_urls)
                ]
                for task in asyncio.as_completed(tasks):
                    await task
                    completed += 1
                    tasks_status[task_id] = (
                        "running", f"{completed}/{total_images}")
            tasks_status[task_id] = (
                "completed", f"/download/{task_id}")
        except Exception as e:
            tasks_status[task_id] = (f"error: {str(e)}", "")


async def get_mangadex_volume(
        prefix: str, manga_id: str, language: str,
        volume_name: str, chapter_names: str, part: int = 0):
    zip_file_name = get_file_name(prefix, volume_name, part, language, manga_id)
    task_id = hashlib.sha256(zip_file_name.encode()).hexdigest()
    chapter_names_decoded = json.loads(chapter_names)
    (status, _res) = tasks_status.get(task_id, ("unknown task", ""))
    if status not in ("scheduled", "running"):
        tasks_status[task_id] = ("scheduled", "")
        asyncio.create_task(
            put_mangadex_volume(
                task_id, prefix, manga_id, language,
                volume_name, chapter_names_decoded, part))
    return await get_task_status(task_id)


async def get_task_status(task_id: str):
    global tasks_status
    (status, res) = tasks_status.get(task_id, ("unknown task", ""))
    ret = {
        "task_id": task_id,
        "status": status
    }
    if status == "completed":
        ret["url"] = res
    if status == "running":
        ret["progress"] = res
    return ret


def get_cbz_file_path(task_id: str):
    global CACHE_DIR
    fname = next((
        fn for fn in os.listdir(CACHE_DIR)
        if fn.startswith(f"{task_id}.") and
        os.path.isfile(os.path.join(CACHE_DIR, fn))), None)
    if fname == None:
        raise Exception("file not found")
    original_name = fname.split('.', 1)[1]
    file_path = os.path.join(CACHE_DIR, fname)
    return (file_path, original_name)
