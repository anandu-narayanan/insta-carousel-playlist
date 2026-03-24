"""
Core views for the Instagram Carousel Playlist app.
Uses Celery background tasks for long-running processing.
"""
import os
import uuid
import mimetypes
from django.shortcuts import render
from django.http import JsonResponse, FileResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django.core.cache import cache
from django.conf import settings


def index(request):
    return render(request, 'core/index.html')


@csrf_exempt
@require_POST
def process(request):
    """
    Kick off a background Celery task.
    Returns immediately with {job_id} — frontend polls /api/status/{job_id}/.
    """
    import json
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'error': 'Invalid JSON body.'}, status=400)

    url = data.get('url', '').strip()
    if not url:
        return JsonResponse({'error': 'No URL provided.'}, status=400)

    job_id = str(uuid.uuid4())
    session_id = job_id[:8]

    # Write initial status to cache
    cache.set(f'job:{job_id}', {
        'step': 0,
        'total': 5,
        'message': 'Starting…',
        'data': None,
        'error': None,
        'done': False,
    }, timeout=3600)

    # Dispatch Celery task
    from .tasks import process_carousel
    process_carousel.delay(job_id, url, session_id)

    return JsonResponse({'job_id': job_id})


@require_GET
def job_status(request, job_id):
    """Poll endpoint — returns current job progress from Redis cache."""
    status = cache.get(f'job:{job_id}')
    if status is None:
        return JsonResponse({'error': 'Job not found or expired.'}, status=404)
    return JsonResponse(status)


def download_file(request, session_id, filepath):
    """Serve a generated file for download with proper Content-Disposition."""
    file_path = os.path.join(settings.MEDIA_ROOT, session_id, filepath)
    if not os.path.exists(file_path):
        raise Http404("File not found.")
    filename = os.path.basename(file_path)
    mime, _ = mimetypes.guess_type(file_path)
    response = FileResponse(
        open(file_path, 'rb'),
        content_type=mime or 'application/octet-stream'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
