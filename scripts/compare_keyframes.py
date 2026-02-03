"""Compare keyframes extracted by ffprobe vs MKV Cues parser."""

import asyncio
import sys
sys.path.insert(0, ".")

from app.services.ffprobe import ffprobe_service
from app.services.mkv_cues import extract_keyframes_from_url


async def compare(url: str, total_size: int | None = None):
    """Compare keyframe extraction methods."""
    print(f"Testing URL: {url}")
    print("=" * 60)
    
    # Extract with MKV Cues (fast)
    print("\n[MKV Cues] Extracting...")
    cues_keyframes = await extract_keyframes_from_url(url, total_size=total_size)
    print(f"[MKV Cues] Found {len(cues_keyframes)} keyframes")
    
    # Extract with ffprobe (slow but accurate)
    print("\n[ffprobe] Extracting...")
    ffprobe_keyframes = await ffprobe_service.extract_keyframes_from_url(url, max_keyframes=5000)
    print(f"[ffprobe] Found {len(ffprobe_keyframes)} keyframes")
    
    # Compare
    print("\n" + "=" * 60)
    print("COMPARISON:")
    print(f"  MKV Cues: {len(cues_keyframes)} keyframes")
    print(f"  ffprobe:  {len(ffprobe_keyframes)} keyframes")
    
    # Show first 10 keyframes from each
    print("\nFirst 10 keyframes:")
    print(f"{'#':<4} {'MKV Cues':>12} {'ffprobe':>12} {'Diff (ms)':>12}")
    print("-" * 44)
    
    max_diff = 0.0
    for i in range(min(10, max(len(cues_keyframes), len(ffprobe_keyframes)))):
        cue = cues_keyframes[i] if i < len(cues_keyframes) else None
        ffp = ffprobe_keyframes[i] if i < len(ffprobe_keyframes) else None
        
        if cue is not None and ffp is not None:
            diff = abs(cue - ffp) * 1000  # ms
            max_diff = max(max_diff, diff)
            print(f"{i:<4} {cue:>12.3f} {ffp:>12.3f} {diff:>12.1f}")
        elif cue is not None:
            print(f"{i:<4} {cue:>12.3f} {'N/A':>12}")
        elif ffp is not None:
            print(f"{i:<4} {'N/A':>12} {ffp:>12.3f}")
    
    # Show keyframes around a specific time (e.g., 130s)
    test_times = [60, 120, 180, 300]
    print("\nKeyframe lookup comparison:")
    print(f"{'Target':>8} {'MKV Cues':>12} {'ffprobe':>12} {'Diff (ms)':>12}")
    print("-" * 48)
    
    import bisect
    for t in test_times:
        # Find closest keyframe <= t
        cue_idx = bisect.bisect_right(cues_keyframes, t) - 1
        ffp_idx = bisect.bisect_right(ffprobe_keyframes, t) - 1
        
        cue = cues_keyframes[cue_idx] if cue_idx >= 0 and cue_idx < len(cues_keyframes) else None
        ffp = ffprobe_keyframes[ffp_idx] if ffp_idx >= 0 and ffp_idx < len(ffprobe_keyframes) else None
        
        if cue is not None and ffp is not None:
            diff = abs(cue - ffp) * 1000
            print(f"{t:>8} {cue:>12.3f} {ffp:>12.3f} {diff:>12.1f}")
        else:
            print(f"{t:>8} {cue or 'N/A':>12} {ffp or 'N/A':>12}")
    
    print(f"\nMax difference in first 10: {max_diff:.1f}ms")
    
    if max_diff < 50:
        print("✓ Keyframes match well (diff < 50ms)")
    else:
        print("✗ Significant difference detected!")


if __name__ == "__main__":
    # Test with local server URL
    media_id = 78  # Change this to your test media
    url = f"http://127.0.0.1:8000/api/v1/stream/raw/{media_id}"
    
    # You can also pass total_size if known
    # total_size = 1162487357
    
    asyncio.run(compare(url))
