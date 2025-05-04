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
import base64
import logging
import re
from ..lib.mangadex_api import get_tags, search_manga, get_manga_cover_96_cached

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _normalize_tag(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9]+', '', s).lower()


async def _get_matching_tag_ids(tag_patterns: list[str]) -> list[str]:
    tags = await get_tags()
    return [
        t.id
        for t in tags
        if any(
            _normalize_tag(pat) in _normalize_tag(t.name)
            for pat in tag_patterns
        )
    ]


def _get_matching_content_ratings(excluded_patterns: list[str]) -> list[str]:
    return [
        cr
        for cr in ["safe", "suggestive", "erotica"]
        if not any(
            _normalize_tag(pat) in cr
            for pat in excluded_patterns
        )
    ]


def _normalize_title(s: str) -> str:
    # [\x00-\x7F] is the ASCII range; ^ = “not”
    return re.sub(r'\s+', ' ',
                  re.sub(r'[^\x00-\x7F]+', '', s.replace("×", " x ")))


async def search_for_manga_dict(
        query: str, included_tags: list[str], excluded_tags: list[str], max_results: int) -> list[dict]:
    included_tag_ids = await _get_matching_tag_ids(included_tags)
    excluded_tag_ids = await _get_matching_tag_ids(excluded_tags)
    content_ratings = _get_matching_content_ratings(excluded_tags)
    search_result = await search_manga(
        query, included_tag_ids, excluded_tag_ids, content_ratings, max_results)
    ret = []
    thumbnail_data_tasks = {}
    for mi in search_result:
        thumbnail_data_tasks[mi.id] = asyncio.create_task(
            get_manga_cover_96_cached(mi.id, mi.cover_id))
        ret.append({
            "title": _normalize_title(mi.title),
            "manga_id": mi.id,
            "authors": mi.authors,
            "cover_url": ""
        })
    for m in ret:
        thumbnail_data = await thumbnail_data_tasks[m["manga_id"]]
        m["cover_url"] = f"data:image/jpeg;base64,{base64.b64encode(thumbnail_data).decode('ascii')}"
    return ret


async def search_for_manga_by_user_query_dict(q: str, max_results: int) -> list[dict]:
    query_words = [w.strip() for w in q.split(' ') if w.strip() != '']
    tag_incl = [w for w in query_words if w[0] == '+']
    tag_excl = [w for w in query_words if w[0] == '-']
    q = " ".join([w for w in query_words if w[0] not in ['-', '+']])
    logger.info(f"q: {q} incl: {tag_incl} excl: {tag_excl}")
    ret = await search_for_manga_dict(q, tag_incl, tag_excl, max_results)
    return ret
