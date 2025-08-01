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



__license__ = "GPLv3"
__copyright__ = "qbit529"
__docformat__ = "restructuredtext en"

from calibre.customize import StoreBase


class MangaDexStore(StoreBase):
    name = "MangaDex"
    version = (1, 2, 1)
    description = "Searches for mangas and converts them to CBZ from a list of known websites."
    author = "qbit529"
    drm_free_only = True
    actual_plugin = "calibre_plugins.store_mangadex.mangadex_plugin:MangaDexStorePlugin"
    formats = ["CBZ"]
