"""
Background job processor using Python threading (no Celery/Redis required).
Job status stored in-memory — works on single-process free hosting.
"""
import threading
import uuid
import os
import traceback
from django.conf import settings
from django.urls import reverse

# In-memory job store — works within a single gunicorn worker
_jobs: dict = {}
_lock = threading.Lock()


def create_job() -> str:
    job_id = str(uuid.uuid4())
    with _lock:
        _jobs[job_id] = {
            'step': 0,
            'total': 5,
            'message': 'Starting…',
            'data': None,
            'error': None,
            'done': False,
        }
    return job_id


def get_job(job_id: str) -> dict | None:
    with _lock:
        return dict(_jobs.get(job_id, {}))


def _set(job_id: str, **kwargs):
    with _lock:
        if job_id in _jobs:
            _jobs[job_id].update(kwargs)


def run_pipeline(job_id: str, url: str, session_id: str):
    """Full 5-step pipeline running in a background thread."""
    from .utils.downloader import download_carousel
    from .utils.merger import merge_media
    from .utils.identifier import identify_songs
    from .utils.youtube import find_and_download_songs
    from .utils.playlist import build_playlist

    session_dir = os.path.join(settings.MEDIA_ROOT, session_id)
    os.makedirs(session_dir, exist_ok=True)

    try:
        _set(job_id, step=1, message='Downloading carousel from Instagram…')
        carousel_data = download_carousel(url, session_id)
        media_files = carousel_data['media_files']
        if not media_files:
            raise ValueError('No media found. Post may be private or restricted.')

        _set(job_id, step=2, message='Merging media and extracting audio…')
        merge_data = merge_media(media_files, session_dir, session_id)
        merged_video = merge_data['merged_video']
        merged_audio = merge_data['merged_audio']

        _set(job_id, step=3, message='Identifying songs via Shazam…')
        songs = identify_songs(merged_audio)

        _set(job_id, step=4, message=f'Finding {len(songs)} songs on YouTube…')
        songs_dir = os.path.join(session_dir, 'songs')
        os.makedirs(songs_dir, exist_ok=True)
        enriched_songs = find_and_download_songs(songs, songs_dir)
        downloaded_mp3_count = len([s for s in enriched_songs if s.get('mp3_path')])

        _set(job_id, step=5, message='Building merged playlist MP3…')
        playlist_path = build_playlist(enriched_songs, session_dir, session_id)

        def download_url(path):
            if not path or not os.path.exists(path):
                return None
            relative_path = os.path.relpath(path, session_dir).replace('\\', '/')
            return reverse('download', args=[session_id, relative_path])

        songs_response = [{
            'title': s.get('title', ''),
            'artist': s.get('artist', ''),
            'artwork': s.get('artwork', ''),
            'shazam_url': s.get('shazam_url', ''),
            'youtube_url': s.get('youtube_url', ''),
            'youtube_title': s.get('youtube_title', ''),
            'youtube_thumbnail': s.get('youtube_thumbnail', ''),
            'duration': s.get('duration', ''),
            'mp3_url': download_url(s.get('mp3_path')),
        } for s in enriched_songs]

        result = {
            'session_id': session_id,
            'post_caption': carousel_data.get('post_caption', ''),
            'media_count': len(media_files),
            'merged_video_url': download_url(merged_video),
            'playlist_url': download_url(playlist_path),
            'songs': songs_response,
            'songs_identified': len([s for s in songs_response if s['title']]),
            'songs_downloaded': downloaded_mp3_count,
            'playlist_unavailable_reason': None if playlist_path else 'No song MP3s were downloaded, so the merged playlist could not be created.',
        }
        _set(job_id, step=5, message='Done!', data=result, done=True)

    except Exception as e:
        traceback.print_exc()
        _set(job_id, error=str(e), done=True)


def start_job(job_id: str, url: str, session_id: str):
    """Spawn a daemon thread to run the pipeline."""
    t = threading.Thread(target=run_pipeline, args=(job_id, url, session_id), daemon=True)
    t.start()
