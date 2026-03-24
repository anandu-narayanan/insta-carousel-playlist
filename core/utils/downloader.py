"""
Instagram carousel downloader using instaloader.
Downloads all media (images + videos) from a carousel post.
"""
import os
import re
import instaloader
from django.conf import settings


def extract_shortcode(url: str) -> str:
    """Extract the shortcode from an Instagram URL."""
    patterns = [
        r'instagram\.com/p/([A-Za-z0-9_-]+)',
        r'instagram\.com/reel/([A-Za-z0-9_-]+)',
        r'instagram\.com/tv/([A-Za-z0-9_-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError(f"Could not extract shortcode from URL: {url}")


def download_carousel(url: str, session_id: str) -> dict:
    """
    Download all media from an Instagram carousel post.
    Returns dict with:
      - shortcode: the post shortcode
      - media_files: list of absolute paths to downloaded files (videos/images)
      - download_dir: directory where files are stored
      - post_caption: caption of the post
    """
    shortcode = extract_shortcode(url)
    download_dir = os.path.join(settings.MEDIA_ROOT, session_id, 'carousel')
    os.makedirs(download_dir, exist_ok=True)

    L = instaloader.Instaloader(
        dirname_pattern=download_dir,
        filename_pattern='{shortcode}_{mediaid}',
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        post_metadata_txt_pattern='',
        quiet=True,
    )

    # Try to log in if credentials are set
    username = getattr(settings, 'INSTAGRAM_USERNAME', '')
    password = getattr(settings, 'INSTAGRAM_PASSWORD', '')
    if username and password:
        try:
            L.login(username, password)
        except Exception as e:
            print(f"[downloader] Login failed (continuing without login): {e}")

    post = instaloader.Post.from_shortcode(L.context, shortcode)
    L.download_post(post, target=download_dir)

    # Collect all downloaded video and image files
    media_files = []
    for f in sorted(os.listdir(download_dir)):
        fpath = os.path.join(download_dir, f)
        if f.endswith('.mp4'):
            media_files.append({'type': 'video', 'path': fpath, 'name': f})
        elif f.endswith(('.jpg', '.jpeg', '.png')):
            media_files.append({'type': 'image', 'path': fpath, 'name': f})

    return {
        'shortcode': shortcode,
        'media_files': media_files,
        'download_dir': download_dir,
        'post_caption': post.caption or '',
    }
