"""Split large files for Telegram upload (no re-encode, no compression)."""

import sys
from pathlib import Path

# Default chunk size: 3.9GB (under Telegram Premium's 4GB limit)
DEFAULT_CHUNK_SIZE = 3900 * 1024 * 1024  # 3.9GB in bytes


def split_file(input_path: str, chunk_size: int = DEFAULT_CHUNK_SIZE) -> list[Path]:
    """
    Split a file into chunks.
    
    Args:
        input_path: Path to the file to split
        chunk_size: Size of each chunk in bytes (default 1.9GB)
    
    Returns:
        List of created chunk file paths
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"File not found: {input_path}")
    
    file_size = input_file.stat().st_size
    num_chunks = (file_size + chunk_size - 1) // chunk_size
    
    print(f"📂 File: {input_file.name}")
    print(f"📊 Size: {file_size / (1024**3):.2f} GB")
    print(f"🔪 Splitting into {num_chunks} parts ({chunk_size / (1024**2):.0f} MB each)")
    print()
    
    output_files = []
    
    with open(input_file, "rb") as f:
        for i in range(num_chunks):
            chunk_path = input_file.with_suffix(f"{input_file.suffix}.{i+1:03d}")
            
            with open(chunk_path, "wb") as chunk_file:
                data = f.read(chunk_size)
                chunk_file.write(data)
            
            output_files.append(chunk_path)
            print(f"   ✅ Created: {chunk_path.name} ({len(data) / (1024**2):.1f} MB)")
    
    print()
    print(f"🎉 Done! Upload these {num_chunks} files to Telegram (grouped together)")
    
    return output_files


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python split_file.py <file_path> [chunk_size_mb]")
        print("Example: python split_file.py movie.mkv 1900")
        sys.exit(1)
    
    file_path = sys.argv[1]
    chunk_mb = int(sys.argv[2]) if len(sys.argv) > 2 else 3900  # 3.9GB for Premium
    chunk_bytes = chunk_mb * 1024 * 1024
    
    split_file(file_path, chunk_bytes)
