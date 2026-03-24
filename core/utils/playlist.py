"""
Playlist builder: merges multiple MP3 files into one using ffmpeg.
"""
import os
import subprocess
import tempfile


def merge_mp3s(mp3_paths: list, output_path: str) -> str:
    """
    Concatenate a list of MP3 files into a single playlist MP3.
    Uses ffmpeg concat demuxer for gapless joining.
    """
    valid = [p for p in mp3_paths if p and os.path.exists(p)]
    if not valid:
        raise ValueError("No valid MP3 files to merge into playlist.")

    if len(valid) == 1:
        import shutil
        shutil.copy(valid[0], output_path)
        return output_path

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        for mp3 in valid:
            f.write(f"file '{mp3}'\n")
        concat_file = f.name

    try:
        result = subprocess.run([
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            output_path,
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"[playlist] ffmpeg error: {result.stderr}")
    finally:
        os.unlink(concat_file)

    return output_path


def build_playlist(songs: list, output_dir: str, session_id: str) -> str | None:
    """
    Given enriched song list (from youtube.py), merge all downloaded MP3s.
    Returns path to merged playlist MP3, or None if no songs available.
    """
    mp3_paths = [s.get('mp3_path') for s in songs if s.get('mp3_path')]
    if not mp3_paths:
        return None

    output_path = os.path.join(output_dir, f'{session_id}_playlist.mp3')
    return merge_mp3s(mp3_paths, output_path)
