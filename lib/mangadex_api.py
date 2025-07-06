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

import os
import asyncio
import urllib
from .utils import download_json, download_bytes, resize_jpeg_bytes
from ..model.mangadex import MangaInfo, VolumeInfo, Tag
from calibre.utils.config import config_dir
from calibre.utils.rapydscript import atomic_write

PLUGIN_ID = 'MangaDex'
THUMBNAIL_CACHE_DIR = os.path.join(
    config_dir, 'plugins', PLUGIN_ID, 'thumbnail_cache')
os.makedirs(THUMBNAIL_CACHE_DIR, exist_ok=True)


async def _get_mangadex(path: str):
    return await download_json(f"https://api.mangadex.org{path}")


async def get_manga_cover_96_cached(manga_id: str, cover_id: str) -> bytes:
    global THUMBNAIL_CACHE_DIR
    file_name = f"{manga_id}.{cover_id}.96.jpg"
    cache_path = os.path.join(
        THUMBNAIL_CACHE_DIR, file_name)
    try:
        with open(cache_path, "rb") as f:
            return f.read()
    except:
        data256 = await get_manga_cover_256(manga_id, cover_id)
        data96 = resize_jpeg_bytes(data256)
        atomic_write(THUMBNAIL_CACHE_DIR, file_name, data96)
    return data96


async def get_manga_cover_256(manga_id: str, cover_id: str) -> bytes:
    fn = f"{manga_id}/{cover_id}"
    data256 = await download_bytes(
        f"https://mangadex.org/covers/{fn}.256.jpg")
    return data256


async def get_manga_info(manga_id: str) -> MangaInfo:
    mng = await _get_mangadex(
        f"/manga/{manga_id}?includes[]=artist&includes[]=author&includes[]=cover_art")
    return MangaInfo(mng['data'])


async def get_volumes_and_chapters(manga_id: str, language: str) -> list[VolumeInfo]:
    url = f"/manga/{manga_id}/aggregate?translatedLanguage[]=" + language
    res = await _get_mangadex(url)
    volumes = res.get("volumes", {})
    # Fix for bug caused by MangaDex API returning empty array instead of empty object
    if isinstance(volumes, list):
        return []
    ret = [VolumeInfo.from_api(v) for v in volumes.values()]
    ret.sort(key=lambda v: v.sort)
    return ret


async def get_volume_and_chapter_by_language_dict(
        manga_id: str, languages: list[str]) -> dict:
    tasks = {}
    for lang in languages:
        tasks[lang] = asyncio.create_task(
            get_volumes_and_chapters(manga_id, lang))
    ret = {}
    for lang in languages:
        dict = [v.to_dict() for v in (await tasks[lang])]
        if len(dict) == 0:
            continue
        ret[lang] = dict
    return ret


async def get_tags() -> list[Tag]:
    res = await _get_mangadex("/manga/tag")
    tags = [Tag(t["attributes"]["name"]["en"], t["id"])
            for t in res["data"]]
    return tags


async def get_chapter_image_urls(chapter_id: str) -> list[str]:
    res = await _get_mangadex("/at-home/server/" +
                              chapter_id + "?forcePort443=false")
    base_url = res["baseUrl"]
    chapter_hash = res["chapter"]["hash"]
    images = res["chapter"]["data"]
    image_urls = list(
        map(lambda img: f"{base_url}/data/{chapter_hash}/{img}", images)
    )
    return image_urls


async def search_manga(
        query: str,
        included_tag_ids: list[str],
        excluded_tag_ids: list[str],
        content_ratings: list[str],
        limit: int) -> list[MangaInfo]:
    encoded_query = urllib.parse.quote(query)
    res = await _get_mangadex(
        "/manga?" +
        "&".join([
            "limit=" + str(limit),
            "offset=0",
            "includes[]=cover_art",
            "includes[]=artist",
            "includes[]=author",
            "order[rating]=desc",
            "includedTagsMode=AND",
            "excludedTagsMode=OR",
            "title=" + encoded_query,
            *[f"includedTags[]={t}" for t in included_tag_ids],
            *[f"excludedTags[]={t}" for t in excluded_tag_ids],
            *[f"contentRating[]={t}" for t in content_ratings],
        ])
    )
    return [MangaInfo(m) for m in res["data"]]
