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
import json
import logging
import os
import shutil
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import unquote, urlparse, parse_qs

from .req.search import search_for_manga_by_user_query_dict
from .req.manga_info import get_manga_info_page
from .req.scrape import get_mangadex_volume, get_task_status, get_cbz_file_path
from .lib.utils import is_localhost

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LocalServer(threading.Thread):
    daemon = True

    def __init__(self, port):
        super().__init__()
        self.port = port
        self.httpd = None
        self.loop = AioLoop()
        self.loop.start()

    def run(self):
        try:
            Handler.parent = self
            self.httpd = ThreadingHTTPServer(('127.0.0.1', self.port), Handler)
            self.httpd.serve_forever(poll_interval=0.5)
        except OSError as e:
            print(f'Calibre plugin server failed: {e}')

    def shutdown(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()


class AioLoop(threading.Thread):
    daemon = True

    def __init__(self):
        super().__init__()
        self.loop = asyncio.new_event_loop()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def schedule(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def shutdown(self):
        self.loop.call_soon_threadsafe(self.loop.stop)


class Handler(BaseHTTPRequestHandler):
    parent = None

    def do_GET(self):
        (ip, port) = self.client_address
        url = urlparse(self.path)
        path = url.path
        qs = parse_qs(url.query)
        path_parts = [p for p in path.split('/') if p != '']
        logger.info(f"processing {path} {qs}")
        if not is_localhost(ip, port):
            self._send(404, b"text/html", b"")
        elif path == '/search' and 'q' in qs and 'max_results' in qs:
            q = unquote(qs['q'][0])
            max_results = int(qs['max_results'][0])
            f = self.parent.loop.schedule(
                search_for_manga_by_user_query_dict(q, max_results))
            body = json.dumps(f.result(), ensure_ascii=False).encode('utf-8')
            self._send(200, b"application/json; charset=utf-8", body)
        elif len(path_parts) == 2 and path_parts[0] == 'manga':
            manga_id = path_parts[1]
            f = self.parent.loop.schedule(get_manga_info_page(manga_id))
            body = f.result().encode('utf-8')
            self._send(200, b"text/html; charset=utf-8", body)
        elif path == '/to_cbz' and {'manga_id', 'language', 'volume_name', 'chapter_names', 'prefix'} <= qs.keys():
            prefix = qs['prefix'][0]
            manga_id = qs['manga_id'][0]
            language = qs['language'][0]
            volume_name = qs['volume_name'][0]
            chapter_names = qs['chapter_names'][0]
            part = 0
            try:
                part = int(qs['part'][0])
            except:
                pass
            f = self.parent.loop.schedule(get_mangadex_volume(
                prefix, manga_id, language, volume_name, chapter_names, part))
            body = json.dumps(f.result(), ensure_ascii=False).encode('utf-8')
            self._send(200, b"application/json; charset=utf-8", body)
        elif len(path_parts) == 3 and path_parts[0] == 'task' and path_parts[2] == 'status':
            task_id = path_parts[1]
            f = self.parent.loop.schedule(get_task_status(task_id))
            body = json.dumps(f.result(), ensure_ascii=False).encode('utf-8')
            self._send(200, b"application/json; charset=utf-8", body)
        elif len(path_parts) == 2 and path_parts[0] == 'download':
            task_id = path_parts[1]
            (file_path, file_name) = get_cbz_file_path(task_id)
            self._send_zip(file_name, file_path)
        else:
            self._send(404, b"text/html", b"")

    def _send(self, code, ctype, body: bytes):
        self.send_response(code)
        self.send_header("Content-Type", ctype.decode())
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_zip(self, file_name, file_path):
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(os.path.getsize(file_path)))
        self.send_header(
            "Content-Disposition",
            f'attachment; filename="{file_name}"'
        )
        self.end_headers()
        with open(file_path, 'rb') as fsrc:
            shutil.copyfileobj(fsrc, self.wfile, length=64000)
        return
