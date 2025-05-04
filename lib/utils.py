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

import urllib.error
import urllib.request
import json
import ssl
import asyncio
import logging
import ipaddress
from typing import Any, Dict, Tuple
from functools import partial
import io
from PIL import Image

logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

parallel_request_limit = 6
req_semaphore = None


def get_req_semaphore() -> asyncio.Semaphore:
    """Return (and lazily create) the per‑event‑loop semaphore."""
    global req_semaphore, parallel_request_limit
    if req_semaphore != None:
        return req_semaphore
    else:
        logger.info("new semaphore")
        req_semaphore = asyncio.Semaphore(parallel_request_limit)
        return req_semaphore


mock_headers = {
    "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:136.0) Gecko/20100101 Firefox/136.0",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "Priority": "u=4",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache"
}


# ––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
# 0.  Shared thread‑pool
#    Python’s default ThreadPoolExecutor size == os.cpu_count() * 5,
#    which is usually plenty; if you want a cap, create your own executor.
# ––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––––
_executor = None   # use the loop's default executor


async def fetch(
    url: str,
    method: str = "GET",
    headers: Dict[str, str] | None = None,
    data: bytes | None = None,
    timeout: int = 15,
    ssl_context: ssl.SSLContext | None = None
) -> Tuple[int, Dict[str, str], bytes]:
    """
    Asynchronously perform an HTTP/HTTPS request using urllib in a thread.
    Returns: (status_code, response_headers_dict, response_body_bytes)
    Raises urllib.error.URLError on DNS / network errors.
    """
    loop = asyncio.get_running_loop()

    # Build the blocking Request object
    req = urllib.request.Request(url, data=data, method=method)
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)

    # urllib.request.urlopen is blocking; run in thread pool
    fn = partial(urllib.request.urlopen, req,
                 timeout=timeout, context=ssl_context)
    try:
        resp = await loop.run_in_executor(_executor, fn)
        with resp:
            body = await loop.run_in_executor(_executor, resp.read)
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, hdrs, body
    except urllib.error.HTTPError as e:
        # Still have headers and body; return them for inspection
        return e.code, dict(e.headers.items()), e.read()

active = 0


async def download_bytes(url: str, **kw) -> Any:
    """Fetch URL and return `json.loads()` of its body."""
    global active
    async with get_req_semaphore():
        active += 1
        logger.info(f"requesting: {url} active: {active}")
        status, _, body = await fetch(url, headers=mock_headers, **kw)
        active -= 1
        if status != 200:
            raise RuntimeError(f"GET {url} → HTTP {status}")
        logger.info(f"requested: {url} ok")
        return body


async def download_json(url: str, **kw) -> Any:
    body = await download_bytes(url, **kw)
    return json.loads(body)


def resize_jpeg_bytes(data: bytes, max_size=(96, 96), quality=85) -> bytes:
    """
    :param data: original JPEG as bytes
    :param max_size: (width, height) max box
    :param quality: JPEG quality for output (1-95)
    :returns: resized JPEG as bytes
    """
    with io.BytesIO(data) as inp:
        with Image.open(inp) as img:
            img = img.convert("RGB")
            img.thumbnail(max_size, Image.Resampling.LANCZOS)
            with io.BytesIO() as out:
                img.save(out, format="JPEG", quality=quality)
                return out.getvalue()


def ensure_image_vertical(image_data: bytes) -> bytes:
    rotated_io = io.BytesIO()
    with Image.open(image_data) as img:
        img_format = img.format if img.format else "PNG"
        if img.width > img.height:
            img = img.rotate(90, expand=True)
        img.save(rotated_io, img_format)
        rotated_io.seek(0)
    return rotated_io


def delete_files_older_than(folder_path: str, hours: float = 12.0) -> None:
    """
    Delete all files in `folder_path` older than `hours` hours.

    :param folder_path: Path to the directory to clean up.
    :param hours: Age threshold in hours; files older than this will be removed.
    """
    import time
    from pathlib import Path
    cutoff = time.time() - hours * 3600
    folder = Path(folder_path)

    if not folder.is_dir():
        raise ValueError(f"Not a directory: {folder_path}")

    for file in folder.iterdir():
        if file.is_file():
            mtime = file.stat().st_mtime
            if mtime < cutoff:
                try:
                    file.unlink()
                    print(f"Deleted: {file.name}")
                except Exception as e:
                    print(f"Could not delete {file.name}: {e}")


def is_localhost(ip: str, port: int | None = None) -> bool:
    """
    Return True if `ip` is a loopback address (localhost).  
    If `port` is given, also verify it’s a valid TCP/UDP port (1–65535).
    """
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False

    # check loopback per RFC 3330/2373
    if not addr.is_loopback:               
        return False                      

    # if a port was provided, ensure it’s in the valid port range
    if port is not None:
        return 1 <= port <= 65535

    return True