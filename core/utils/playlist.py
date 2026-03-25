"""
Playlist builder: merges multiple MP3 files into one using ffmpeg.
"""
import os
import subprocess
import tempfile


def normalize_mp3(input_path: str, output_path: str) -> str:
    """Re-encode an MP3 into a consistent format before merging."""
    result = subprocess.run([
        'ffmpeg', '-y',
        '-i', input_path,
        '-vn',
        '-ar', '44100',
        '-ac', '2',
        '-b:a', '192k',
        output_path,
    ], capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"[playlist] normalize error: {result.stderr}")
    return output_path


def merge_mp3s(mp3_paths: list, output_path: str) -> str:
    """
    Concatenate a list of MP3 files into a single playlist MP3.
    Re-encodes inputs first so merging is reliable across sources.
    """
    valid = [p for p in mp3_paths if p and os.path.exists(p)]
    if not valid:
        raise ValueError("No valid MP3 files to merge into playlist.")

    if len(valid) == 1:
        import shutil
        shutil.copy(valid[0], output_path)
        return output_path

    normalized_dir = tempfile.mkdtemp()
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
        normalized_paths = []
        for idx, mp3 in enumerate(valid):
            normalized_path = os.path.join(normalized_dir, f'part_{idx:03d}.mp3')
            normalize_mp3(mp3, normalized_path)
            normalized_paths.append(normalized_path)
            f.write(f"file '{normalized_path}'\n")
        concat_file = f.name

    try:
        result = subprocess.run([
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c:a', 'libmp3lame',
            '-b:a', '192k',
            output_path,
        ], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"[playlist] ffmpeg error: {result.stderr}")
    finally:
        os.unlink(concat_file)
        for path in locals().get('normalized_paths', []):
            if os.path.exists(path):
                os.unlink(path)
        if os.path.isdir(normalized_dir):
            os.rmdir(normalized_dir)

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
