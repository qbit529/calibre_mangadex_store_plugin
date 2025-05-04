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

from datetime import date


def is_number(s: str) -> bool:
    try:
        float(s)
        return True
    except ValueError:
        return False


class MangaInfo:
    """
    Class to parse and store manga information from a raw API response dict.
    """

    def __init__(self, manga_data: dict):
        # Basic identifiers
        self.id = manga_data.get('id')
        attributes = manga_data.get('attributes', {})
        relationships = manga_data.get('relationships', [])

        # Title handling
        title_lang = next(iter(attributes.get('title', {})), None)
        primary_title = attributes.get('title', {}).get(title_lang, '')
        # Find English alternative title if exists
        alt_title = next(
            (t.get('en') for t in attributes.get('altTitles', []) if 'en' in t),
            primary_title
        )
        if primary_title != alt_title:
            self.title = f"{primary_title} | {alt_title}"
        else:
            self.title = primary_title

        # Authors and artists
        self.authors = list({
            r['attributes']['name']
            for r in relationships
            if r.get('type') in ('author', 'artist') and 'attributes' in r
        })

        # Tags (English names)
        self.tags = ["Manga"] + [
            tag['attributes']['name']['en']
            for tag in attributes.get('tags', [])
            if tag.get('attributes', {}).get('name', {}).get('en')
        ]

        # Cover art filename
        self.cover_id = next(
            (r['attributes']['fileName']
             for r in relationships if r.get('type') == 'cover_art'),
            ''
        )

        # Description and year
        self.description = attributes.get('description', {}).get('en', '')
        year_value = attributes.get('year')
        try:
            self.year = int(year_value)
        except (TypeError, ValueError):
            self.year = None

        # Content rating
        self.content_rating = attributes.get('contentRating', None)

        # Available languages
        self.translated_languages = attributes.get(
            'availableTranslatedLanguages', None)

    def to_dict(self) -> dict:
        """
        Returns a dictionary representation of the MangaInfo instance.
        """
        return {
            'id': self.id,
            'title': self.title,
            'authors': self.authors,
            'tags': self.tags,
            'cover_id': self.cover_id,
            'description': self.description,
            'year': self.year,
            'content_rating': self.content_rating,
            'translated_languages': self.translated_languages
        }

    def _get_meta_volume_name(volume_name: str, part: int) -> str:
        parts = ''
        if part > 0:
            parts = f'Part{str(part)} '
        if is_number(volume_name):
            return f'Vol{volume_name} {parts}'
        return f'No Volume({date.today()}) {parts}'

    def to_comic_info_xml(self, volume_name: str, lang: str, part: int = 0) -> str:
        volume_name_final = MangaInfo._get_meta_volume_name(volume_name, part)
        return f'''
            <?xml version="1.0" encoding="utf-8"?>
            <ComicInfo>
                <Title>{self.title} {volume_name_final}{lang.upper()}</Title>
                <Series>{self.title}</Series>
                <Volume>{volume_name}</Volume>
                <Summary>{self.description}</Summary>
                <Writer>{' & '.join(self.authors)}</Writer>
                <Year>{self.year}</Year>
                <Genre>{' & '.join(self.tags)}</Genre>
                <Language>{lang}</Language>
            </ComicInfo>
        '''.strip()

    def to_comic_book_info_json(self, volume_name: str, lang: str, part: int = 0) -> dict:
        volume_name_final = MangaInfo._get_meta_volume_name(volume_name, part)
        return {
            "ComicBookInfo/1.0": {
                "title": f"{self.title} {volume_name_final}{lang.upper()}",
                "series": self.title,
                "publicationYear": self.year,
                "language": lang,
                "lang": lang,
                "tags": self.tags,
                "comments": self.description,
                "volume": volume_name,
                "credits": [{"person": a, "role": "Writer"} for a in self.authors]
            }
        }


class ChapterInfo:
    def __init__(self, name: str, chapter_id_variants: list[str]):
        self.name = name
        # a chapter can have multiple ids if multiple translations for the same language were made
        self.chapter_id_variants = chapter_id_variants
        try:
            self.sort = float(name)
        except (ValueError, TypeError):
            self.sort = 1e6

    def to_dict(self) -> dict:
        return {
            "type": "ChapterInfo",
            "name": self.name,
            "chapter_id_variants": self.chapter_id_variants
        }

    @classmethod
    def from_api(self, obj: dict) -> "ChapterInfo":
        chapter_ids = [obj['id']] + obj['others']
        return ChapterInfo(obj['chapter'], chapter_ids)


class VolumeInfo:
    def __init__(self, name: str, chapters: list[ChapterInfo]):
        self.name = name
        self.chapters = chapters
        self.chapters.sort(key=lambda c: c.sort)
        try:
            self.sort = float(name)
        except (ValueError, TypeError):
            self.sort = 1e6

    def to_dict(self) -> dict:
        return {
            "type": "VolumeInfo",
            "name": self.name,
            "chapters": [c.to_dict() for c in self.chapters]
        }

    @classmethod
    def from_api(self, obj: dict) -> "VolumeInfo":
        chapters = [ChapterInfo.from_api(ch)
                    for ch in obj['chapters'].values()]
        return VolumeInfo(obj['volume'], chapters)


class Tag:
    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id

    def to_dict(self) -> dict:
        return {
            "type": "Tag",
            "name": self.name,
            "id": self.id
        }
