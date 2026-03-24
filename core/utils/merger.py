"""
Audio/video merger using ffmpeg.
- Merges carousel videos into one MP4
- Creates image slideshows from images
- Extracts audio as WAV for song identification
"""
import os
import subprocess
import tempfile


def _run(cmd: list, label: str = "ffmpeg"):
    """Run an ffmpeg command and raise on error."""
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[{label}] Error: {result.stderr}")
    return result


def merge_videos(video_paths: list, output_path: str) -> str:
    """Concatenate multiple MP4 videos into one using ffmpeg."""
    if len(video_paths) == 1:
        import shutil
        shutil.copy(video_paths[0], output_path)
        return output_path

    # Write concat list to a temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        for vp in video_paths:
            f.write(f"file '{vp}'\n")
        concat_file = f.name

    try:
        _run([
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            output_path,
        ], label="merge_videos")
    finally:
        os.unlink(concat_file)

    return output_path


def images_to_slideshow(image_paths: list, output_path: str, duration_per_image: int = 3) -> str:
    """Convert a list of images into a slideshow MP4 (no audio)."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        for ip in image_paths:
            f.write(f"file '{ip}'\n")
            f.write(f"duration {duration_per_image}\n")
        concat_file = f.name

    try:
        _run([
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-vf', 'scale=1080:1080:force_original_aspect_ratio=decrease,pad=1080:1080:(ow-iw)/2:(oh-ih)/2',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            output_path,
        ], label="images_to_slideshow")
    finally:
        os.unlink(concat_file)

    return output_path


def merge_media(media_files: list, output_dir: str, session_id: str) -> dict:
    """
    Given a list of media file dicts (from downloader.py), produce:
    - merged_video: path to merged MP4
    - merged_audio: path to extracted WAV
    """
    videos = [m['path'] for m in media_files if m['type'] == 'video']
    images = [m['path'] for m in media_files if m['type'] == 'image']

    merged_video_path = os.path.join(output_dir, f'{session_id}_merged.mp4')
    merged_audio_path = os.path.join(output_dir, f'{session_id}_audio.wav')

    if videos:
        # If mix of images and videos, convert images first and prepend
        if images:
            slide_path = os.path.join(output_dir, f'{session_id}_slides.mp4')
            images_to_slideshow(images, slide_path)
            all_videos = [slide_path] + videos
        else:
            all_videos = videos
        merge_videos(all_videos, merged_video_path)
    elif images:
        images_to_slideshow(images, merged_video_path)
    else:
        raise ValueError("No video or image files found to merge.")

    # Extract audio from merged video
    _run([
        'ffmpeg', '-y',
        '-i', merged_video_path,
        '-vn',
        '-acodec', 'pcm_s16le',
        '-ar', '44100',
        '-ac', '2',
        merged_audio_path,
    ], label="extract_audio")

    return {
        'merged_video': merged_video_path,
        'merged_audio': merged_audio_path,
    }
