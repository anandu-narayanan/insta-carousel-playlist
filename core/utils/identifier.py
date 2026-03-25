"""
Song identification using ShazamIO.
Splits audio into chunks and identifies each unique song.
"""
import asyncio
import os
import subprocess
import tempfile
from shazamio import Shazam


def split_audio_into_chunks(
    audio_path: str,
    chunk_duration: int = 18,
    stride: int = 12,
) -> list:
    """Split a WAV file into overlapping chunks for better song coverage."""
    # Get total duration via ffprobe
    result = subprocess.run(
        ['ffprobe', '-v', 'quiet', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
        capture_output=True, text=True
    )
    try:
        total_duration = float(result.stdout.strip())
    except (ValueError, AttributeError):
        total_duration = 60.0  # fallback

    chunks = []
    start = 0
    idx = 0
    tmp_dir = tempfile.mkdtemp()

    while start < total_duration:
        chunk_path = os.path.join(tmp_dir, f'chunk_{idx:03d}.wav')
        subprocess.run([
            'ffmpeg', '-y',
            '-i', audio_path,
            '-ss', str(start),
            '-t', str(chunk_duration),
            '-acodec', 'pcm_s16le',
            chunk_path,
        ], capture_output=True)
        if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 1000:
            chunks.append({'path': chunk_path, 'start': start})
        start += stride
        idx += 1

    return chunks


async def _identify_chunk(shazam: Shazam, chunk_path: str) -> dict | None:
    """Identify a single audio chunk using ShazamIO."""
    try:
        out = await shazam.recognize(chunk_path)
        track = out.get('track')
        if track:
            title = track.get('title', 'Unknown')
            artist = track.get('subtitle', 'Unknown Artist')
            # Get Apple Music / Shazam URL if available
            share = track.get('share', {})
            shazam_url = share.get('href', '')
            # Try to get album art
            images = track.get('images', {})
            artwork = images.get('coverart', '')
            return {
                'title': title,
                'artist': artist,
                'shazam_url': shazam_url,
                'artwork': artwork,
            }
    except Exception as e:
        print(f"[identifier] Chunk identification failed: {e}")
    return None


async def _identify_all(chunks: list) -> list:
    """Run Shazam identification on all chunks, deduplicate by title."""
    shazam = Shazam()
    results = []
    seen = set()

    for chunk in chunks:
        result = await _identify_chunk(shazam, chunk['path'])
        if result:
            key = (result['title'].lower(), result['artist'].lower())
            if key not in seen:
                seen.add(key)
                results.append(result)
        # Small delay to be respectful to the Shazam API
        await asyncio.sleep(0.5)

    return results


def identify_songs(audio_path: str) -> list:
    """
    Identify all unique songs in an audio file.
    Returns a list of dicts: [{title, artist, shazam_url, artwork}, ...]
    """
    print(f"[identifier] Splitting audio: {audio_path}")
    chunks = split_audio_into_chunks(audio_path, chunk_duration=18, stride=12)
    print(f"[identifier] Got {len(chunks)} chunks, running Shazam...")

    songs = asyncio.run(_identify_all(chunks))

    # Cleanup tmp chunks
    for chunk in chunks:
        try:
            os.unlink(chunk['path'])
        except Exception:
            pass

    print(f"[identifier] Identified {len(songs)} unique songs")
    return songs
