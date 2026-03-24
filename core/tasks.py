"""
Celery background task: runs the full 5-step carousel processing pipeline.
"""
import os
import traceback
from celery import shared_task
from django.core.cache import cache
from django.conf import settings

from .utils.downloader import download_carousel
from .utils.merger import merge_media
from .utils.identifier import identify_songs
from .utils.youtube import find_and_download_songs
from .utils.playlist import build_playlist


def set_status(job_id, step, total, message, data=None, error=None):
    """Update job status in cache."""
    cache.set(f'job:{job_id}', {
        'step': step,
        'total': total,
        'message': message,
        'data': data,
        'error': error,
        'done': step >= total or error is not None,
    }, timeout=3600)  # 1 hour TTL


@shared_task(bind=True)
def process_carousel(self, job_id: str, url: str, session_id: str):
    """Full pipeline: download → merge → identify → YouTube → playlist."""
    session_dir = os.path.join(settings.MEDIA_ROOT, session_id)
    os.makedirs(session_dir, exist_ok=True)

    try:
        # ── Step 1: Download ───────────────────────────────────────
        set_status(job_id, 1, 5, 'Downloading carousel from Instagram…')
        carousel_data = download_carousel(url, session_id)
        media_files = carousel_data['media_files']
        if not media_files:
            raise ValueError('No media found. Post may be private or restricted.')

        # ── Step 2: Merge ──────────────────────────────────────────
        set_status(job_id, 2, 5, 'Merging media and extracting audio…')
        merge_data = merge_media(media_files, session_dir, session_id)
        merged_video = merge_data['merged_video']
        merged_audio = merge_data['merged_audio']

        # ── Step 3: Identify songs ─────────────────────────────────
        set_status(job_id, 3, 5, 'Identifying songs via Shazam…')
        songs = identify_songs(merged_audio)

        # ── Step 4: YouTube search + download ──────────────────────
        set_status(job_id, 4, 5, f'Finding {len(songs)} songs on YouTube…')
        songs_dir = os.path.join(session_dir, 'songs')
        os.makedirs(songs_dir, exist_ok=True)
        enriched_songs = find_and_download_songs(songs, songs_dir)

        # ── Step 5: Build playlist ─────────────────────────────────
        set_status(job_id, 5, 5, 'Building merged playlist MP3…')
        playlist_path = build_playlist(enriched_songs, session_dir, session_id)

        # ── Build result ───────────────────────────────────────────
        def media_url(path):
            if not path or not os.path.exists(path):
                return None
            rel = os.path.relpath(path, settings.MEDIA_ROOT).replace('\\', '/')
            return f'{settings.MEDIA_URL}{rel}'

        songs_response = [{
            'title': s.get('title', ''),
            'artist': s.get('artist', ''),
            'artwork': s.get('artwork', ''),
            'shazam_url': s.get('shazam_url', ''),
            'youtube_url': s.get('youtube_url', ''),
            'youtube_title': s.get('youtube_title', ''),
            'youtube_thumbnail': s.get('youtube_thumbnail', ''),
            'duration': s.get('duration', ''),
            'mp3_url': media_url(s.get('mp3_path')),
        } for s in enriched_songs]

        result = {
            'session_id': session_id,
            'post_caption': carousel_data.get('post_caption', ''),
            'media_count': len(media_files),
            'merged_video_url': media_url(merged_video),
            'playlist_url': media_url(playlist_path),
            'songs': songs_response,
            'songs_identified': len([s for s in songs_response if s['title']]),
        }

        set_status(job_id, 5, 5, 'Done!', data=result)

    except Exception as e:
        traceback.print_exc()
        set_status(job_id, 0, 5, str(e), error=str(e))
