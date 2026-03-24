"""
Core views for the Instagram Carousel Playlist app.
Uses in-process background jobs for single-service hosting.
"""
import json
import mimetypes
import os

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from . import jobs


def index(request):
    return render(request, "core/index.html")


@csrf_exempt
@require_POST
def process(request):
    """Kick off a background job and return a job id for polling."""
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    url = data.get("url", "").strip()
    if not url:
        return JsonResponse({"error": "No URL provided."}, status=400)

    job_id = jobs.create_job()
    session_id = job_id[:8]
    jobs.start_job(job_id, url, session_id)

    return JsonResponse({"job_id": job_id})


@require_GET
def job_status(request, job_id):
    """Poll job status from the in-memory job store."""
    job = jobs.get_job(job_id)
    if not job:
        return JsonResponse({"error": "Job not found"}, status=404)

    return JsonResponse(job)


def download_file(request, session_id, filepath):
    """Serve a generated file for download with proper Content-Disposition."""
    session_root = os.path.abspath(os.path.join(settings.MEDIA_ROOT, session_id))
    file_path = os.path.abspath(os.path.join(session_root, filepath))

    if os.path.commonpath([session_root, file_path]) != session_root:
        raise Http404("File not found.")

    if not os.path.exists(file_path):
        raise Http404("File not found.")

    filename = os.path.basename(file_path)
    mime, _ = mimetypes.guess_type(file_path)
    response = FileResponse(
        open(file_path, "rb"),
        content_type=mime or "application/octet-stream",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
