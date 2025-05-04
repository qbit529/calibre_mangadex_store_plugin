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


from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import urllib.parse
import json

from calibre import browser
from calibre.gui2.store import StorePlugin
from calibre.gui2.store.search_result import SearchResult
from calibre.gui2.store.web_store_dialog import WebStoreDialog

from .server import LocalServer

USER_AGENT = "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko"
port = 0

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MangaDexStorePlugin(StorePlugin):
    def __init__(self, *args, **kwargs):
        super(MangaDexStorePlugin, self).__init__(*args, **kwargs)
        global port
        self.port = 50051
        self.server = LocalServer(self.port)
        port = self.port
        self.server.start()
        logger.info(f"MangaDex :: started server on port {self.port}")

    def open(self, parent=None, detail_item=None, external=False):
        url = f"http://localhost:{port}"
        d = WebStoreDialog(self.gui, url, parent, detail_item)
        d.setWindowTitle(self.name)
        d.exec_()

    @staticmethod
    def search(query, max_results=10, timeout=60):
        encoded_query = urllib.parse.quote(query)
        search_url = f"http://localhost:{port}/search?q={encoded_query}&max_results={max_results}"
        logger.info(search_url)
        br = browser(user_agent=USER_AGENT)
        raw = br.open(search_url, timeout=timeout).read()
        res = json.loads(raw)
        for jres in res:
            sr = SearchResult()
            sr.title = jres['title']
            sr.author = " & ".join(jres['authors'])
            sr.formats = 'CBZ'
            sr.cover_url = jres['cover_url']
            sr.drm = SearchResult.DRM_UNLOCKED
            sr.detail_item = f"http://localhost:{port}/manga/{jres['manga_id']}"
            yield sr
