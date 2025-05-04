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

import base64
import json
from ..lib.mangadex_api import get_manga_info, get_volume_and_chapter_by_language_dict, get_manga_cover_256
from calibre_plugins.store_mangadex import get_resources

PAGE_TEMPLATE: str = (
    get_resources('templates/download_page.tpl.html')
    .decode('utf-8')
)

max_volume_size = 20
language_whitelist = ['en', 'es', 'es-la', 'ro']


async def get_manga_info_page(manga_id: str):
    global language_whitelist, max_volume_size, PAGE_TEMPLATE
    manga_info = await get_manga_info(manga_id)
    page = manga_info.to_dict()
    thumbnail_data = await get_manga_cover_256(
        manga_id, manga_info.cover_id)
    page['cover_url'] = f"data:image/jpeg;base64,{base64.b64encode(thumbnail_data).decode('ascii')}"
    langs = [l for l in manga_info.translated_languages if l in language_whitelist]
    page['translated_languages'] = langs
    page['volumes'] = await get_volume_and_chapter_by_language_dict(
        manga_id, langs)
    page['max_volume_size'] = max_volume_size
    html_str = PAGE_TEMPLATE.replace('{/* manga_json */}', json.dumps(page))
    return html_str
