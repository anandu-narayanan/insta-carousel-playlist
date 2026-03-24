"""
YouTube search and audio download utilities.
- Searches YouTube for a song by title + artist using yt-dlp's native ytsearch
- Downloads the best audio stream as MP3 using yt-dlp
"""
import os
import re
import yt_dlp


def search_youtube(title: str, artist: str) -> dict | None:
    """
    Search YouTube for a song using yt-dlp's ytsearch (more reliable than youtube-search-python).
    Returns dict: {title, url, thumbnail, duration}
    """
    query = f"{title} {artist} audio"
    print(f"[youtube] yt-dlp search: {query}")

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,      # don't download, just get metadata
        'skip_download': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch5:{query}", download=False)
            entries = info.get('entries', [])
            if not entries:
                print(f"[youtube] No results for: {query}")
                return None

            # Prefer entries whose uploader contains topic/vevo/official
            for entry in entries:
                uploader = (entry.get('uploader') or '').lower()
                etitle = (entry.get('title') or '').lower()
                if any(k in uploader for k in ['topic', 'vevo', 'official']) or \
                   any(k in etitle for k in ['official audio', 'official video', 'lyrics']):
                    return _entry_to_dict(entry)

            # Fallback: first result
            return _entry_to_dict(entries[0])

    except Exception as e:
        print(f"[youtube] Search failed for '{query}': {e}")
        return None


def _entry_to_dict(entry: dict) -> dict:
    vid_id = entry.get('id', '')
    url = f"https://www.youtube.com/watch?v={vid_id}" if vid_id else entry.get('url', '')
    thumbnails = entry.get('thumbnails') or []
    thumbnail = thumbnails[-1].get('url', '') if thumbnails else ''

    # Duration in seconds → mm:ss string
    dur_secs = entry.get('duration') or 0
    duration = f"{int(dur_secs)//60}:{int(dur_secs)%60:02d}" if dur_secs else ''

    return {
        'title': entry.get('title', ''),
        'url': url,
        'thumbnail': thumbnail,
        'duration': duration,
    }


def download_audio(youtube_url: str, output_dir: str, filename: str) -> str | None:
    """
    Download the best audio stream from a YouTube URL as MP3.
    Returns the path to the downloaded MP3, or None on failure.
    """
    safe_name = re.sub(r'[^\w\-_]', '_', filename)
    output_template = os.path.join(output_dir, f'{safe_name}.%(ext)s')
    mp3_path = os.path.join(output_dir, f'{safe_name}.mp3')

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([youtube_url])
        if os.path.exists(mp3_path):
            print(f"[youtube] Downloaded: {mp3_path}")
            return mp3_path
        else:
            # yt-dlp sometimes names differently — scan dir for the safe_name
            for f in os.listdir(output_dir):
                if f.startswith(safe_name) and f.endswith('.mp3'):
                    return os.path.join(output_dir, f)
    except Exception as e:
        print(f"[youtube] Download failed for {youtube_url}: {e}")

    return None


def find_and_download_songs(songs: list, output_dir: str) -> list:
    """
    Given a list of identified songs (from identifier.py),
    search YouTube and download each as MP3.
    Returns enriched song list with youtube_url, mp3_path, thumbnail.
    """
    enriched = []
    for i, song in enumerate(songs):
        title = song.get('title', 'Unknown')
        artist = song.get('artist', 'Unknown')
        print(f"[youtube] Processing song {i+1}: {title} - {artist}")

        yt_result = search_youtube(title, artist)
        if yt_result and yt_result.get('url'):
            safe_title = re.sub(r'[^\w]', '_', title)[:30]
            filename = f"song_{i:02d}_{safe_title}"
            mp3_path = download_audio(yt_result['url'], output_dir, filename)
            enriched.append({
                **song,
                'youtube_url': yt_result['url'],
                'youtube_title': yt_result['title'],
                'youtube_thumbnail': yt_result.get('thumbnail', ''),
                'duration': yt_result.get('duration', ''),
                'mp3_path': mp3_path,
            })
            print(f"[youtube] ✓ {title}: {yt_result['url']}")
        else:
            print(f"[youtube] ✗ No result for: {title} - {artist}")
            enriched.append({
                **song,
                'youtube_url': '',
                'youtube_title': '',
                'youtube_thumbnail': '',
                'duration': '',
                'mp3_path': None,
            })

    return enriched

