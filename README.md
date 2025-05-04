# calibre_mangadex_store_plugin
A calibre plugin to access MangaDex and download issues in CBZ format with metadata

**License:** GPL‑3.0

**Installation:**
1. Zip the plugin folder.  
2. In Calibre Preferences → Plugins → Load plugin from file, select the ZIP.  
3. Restart Calibre.

## Features

- **Search Titles**: Search MangaDex by title.  
- **Tag Filtering**: Specify tags to include (`+tag`) or exclude (`-tag`).
- **Connection Throttling**: Fixed semaphore limits concurrent requests to avoid rate limiting (not configurable).  
- **CBZ Download**: Downloads chapters as CBZ archives.  
- **Metadata**: Embeds `ComicInfo.xml` and `ComicBookInfo` metadata in each CBZ.
- **Auto-rotation**: Large panels are automatically rotated 90 degrees for better viewing on smaller ebook readers.

## Usage

1. In Calibre, open the plugin search panel.  
2. Enter free-text query and tag filters separately:  
   - **Query:** `one piece`  
   - **Tags:** `+adventure -horror`  
3. Select desired chapters and click **Download**.  
4. Imported CBZ with metadata appears in your library.

## Configuration

- **Semaphore Limit**: Internally fixed to throttle requests; user cannot modify.

## Development & Testing

- Plugin tested by zipping folder and loading into Calibre; no automated tests yet.

## Future Enhancements

- Add automated test suite.  
- Configutable language whitelist.
