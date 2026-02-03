"""Debug keyframe sync: compare MKV Cues keyframe vs FFmpeg actual start."""

import asyncio
import subprocess
import sys
sys.path.insert(0, ".")

from app.services.mkv_cues import extract_keyframes_from_url
import bisect


async def debug_seek(url: str, seek_time: float, total_size: int | None = None):
    """Debug a specific seek operation."""
    print(f"=" * 60)
    print(f"DEBUG SEEK: t={seek_time}s")
    print(f"=" * 60)
    
    # 1. Get keyframes from MKV Cues
    print("\n[1] Extracting keyframes via MKV Cues...")
    keyframes = await extract_keyframes_from_url(url, total_size=total_size)
    print(f"    Found {len(keyframes)} keyframes")
    
    # 2. Find keyframe for seek time (binary search)
    idx = bisect.bisect_right(keyframes, seek_time) - 1
    if idx >= 0:
        mkv_keyframe = keyframes[idx]
    else:
        mkv_keyframe = 0.0
    print(f"\n[2] MKV Cues keyframe for t={seek_time}s:")
    print(f"    → {mkv_keyframe}s (idx={idx})")
    
    # Show nearby keyframes
    print(f"\n    Nearby keyframes:")
    for i in range(max(0, idx-2), min(len(keyframes), idx+3)):
        marker = " ←" if i == idx else ""
        print(f"      [{i}] {keyframes[i]:.3f}s{marker}")
    
    # 3. Get actual first frame from FFmpeg output
    print(f"\n[3] FFmpeg actual first frame PTS...")
    play_url = url.replace("/stream/raw/", "/stream/play/") + f"?t={seek_time}"
    
    cmd = [
        "C:\\Program Files\\ffmpeg\\bin\\ffprobe.exe",
        "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "frame=pts_time",
        "-of", "csv=p=0",
        "-read_intervals", "%+#1",  # First frame only
        play_url,
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and result.stdout.strip():
            first_pts = float(result.stdout.strip().split('\n')[0])
            print(f"    → First frame PTS: {first_pts}s")
            
            # 4. Compare
            diff_ms = abs(mkv_keyframe - first_pts) * 1000
            print(f"\n[4] COMPARISON:")
            print(f"    MKV Cues keyframe: {mkv_keyframe:.3f}s")
            print(f"    FFmpeg first PTS:  {first_pts:.3f}s")
            print(f"    Difference:        {diff_ms:.1f}ms")
            
            if diff_ms < 50:
                print(f"    ✓ MATCH (diff < 50ms)")
            else:
                print(f"    ✗ MISMATCH!")
                # Try to find what keyframe FFmpeg actually used
                ffmpeg_idx = bisect.bisect_right(keyframes, first_pts) - 1
                if ffmpeg_idx >= 0 and ffmpeg_idx != idx:
                    print(f"    FFmpeg used keyframe idx={ffmpeg_idx}: {keyframes[ffmpeg_idx]:.3f}s")
        else:
            print(f"    Error: {result.stderr}")
    except Exception as e:
        print(f"    Error: {e}")


if __name__ == "__main__":
    media_id = 78
    url = f"http://127.0.0.1:8000/api/v1/stream/raw/{media_id}"
    
    # Test various seek times
    seek_times = [130, 187, 60, 300]
    
    if len(sys.argv) > 1:
        seek_times = [float(sys.argv[1])]
    
    for t in seek_times:
        asyncio.run(debug_seek(url, t))
        print("\n")
