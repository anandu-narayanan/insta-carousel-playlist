"""
Core views for the Instagram Carousel Playlist app.
Handles the full pipeline: download → merge → identify → YouTube → playlist.
"""
import os
import uuid
import mimetypes
from django.shortcuts import render
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

from .utils.downloader import download_carousel
from .utils.merger import merge_media
from .utils.identifier import identify_songs
from .utils.youtube import find_and_download_songs
from .utils.playlist import build_playlist


def index(request):
    return render(request, 'core/index.html')


@csrf_exempt
@require_POST
def process(request):
    """
    Main pipeline endpoint.
    POST body: { "url": "https://www.instagram.com/p/..." }
    Returns full JSON result with songs, YouTube links, download URLs.
    """
    import json
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    url = data.get('url', '').strip()
    if not url:
        return JsonResponse({'error': 'No URL provided.'}, status=400)

    session_id = str(uuid.uuid4())[:8]
    session_dir = os.path.join(settings.MEDIA_ROOT, session_id)
    os.makedirs(session_dir, exist_ok=True)

    try:
        # ── Step 1: Download carousel ──────────────────────────────────
        carousel_data = download_carousel(url, session_id)
        media_files = carousel_data['media_files']
        if not media_files:
            return JsonResponse({'error': 'No media found in this post. It may be private or restricted.'}, status=400)

        # ── Step 2: Merge media + extract audio ──────────────────────
        merge_data = merge_media(media_files, session_dir, session_id)
        merged_video = merge_data['merged_video']
        merged_audio = merge_data['merged_audio']

        # ── Step 3: Identify songs ───────────────────────────────────
        songs = identify_songs(merged_audio)

        # ── Step 4: Find YouTube links + download songs ───────────────
        songs_dir = os.path.join(session_dir, 'songs')
        os.makedirs(songs_dir, exist_ok=True)
        enriched_songs = find_and_download_songs(songs, songs_dir)

        # ── Step 5: Build playlist ────────────────────────────────────
        playlist_path = build_playlist(enriched_songs, session_dir, session_id)

        # ── Build response ────────────────────────────────────────────
        def media_url(path):
            if not path or not os.path.exists(path):
                return None
            rel = os.path.relpath(path, settings.MEDIA_ROOT).replace('\\', '/')
            return f'{settings.MEDIA_URL}{rel}'

        songs_response = []
        for s in enriched_songs:
            songs_response.append({
                'title': s.get('title', ''),
                'artist': s.get('artist', ''),
                'artwork': s.get('artwork', ''),
                'shazam_url': s.get('shazam_url', ''),
                'youtube_url': s.get('youtube_url', ''),
                'youtube_title': s.get('youtube_title', ''),
                'youtube_thumbnail': s.get('youtube_thumbnail', ''),
                'duration': s.get('duration', ''),
                'mp3_url': media_url(s.get('mp3_path')),
            })

        return JsonResponse({
            'session_id': session_id,
            'post_caption': carousel_data.get('post_caption', ''),
            'media_count': len(media_files),
            'merged_video_url': media_url(merged_video),
            'playlist_url': media_url(playlist_path),
            'songs': songs_response,
            'songs_identified': len([s for s in songs_response if s['title']]),
        })

    except Exception as e:
        import traceback
        print(f"[process] Error: {e}")
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


def download_file(request, session_id, filename):
    """Serve a generated file for download."""
    file_path = os.path.join(settings.MEDIA_ROOT, session_id, filename)
    if not os.path.exists(file_path):
        raise Http404("File not found.")
    mime, _ = mimetypes.guess_type(file_path)
    response = FileResponse(open(file_path, 'rb'), content_type=mime or 'application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
