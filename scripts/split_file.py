"""Split large files for Telegram upload (no re-encode, no compression).

Usage:
    GUI:  python split_file.py
    CLI:  python split_file.py file1.mkv file2.mkv [--chunk-mb 3900]
"""

import sys
import threading
from pathlib import Path

DEFAULT_CHUNK_MB = 3900  # 3.9 GB — under Telegram Premium 4 GB limit
READ_BUFFER = 64 * 1024 * 1024  # 64 MB read buffer


def split_file(
    input_path: str,
    chunk_size: int,
    on_progress: callable = None,
) -> list[Path]:
    """Split a single file into chunks. Returns list of created paths."""
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    file_size = input_file.stat().st_size
    num_chunks = (file_size + chunk_size - 1) // chunk_size
    output_files: list[Path] = []
    bytes_written_total = 0

    with open(input_file, "rb") as f:
        for i in range(num_chunks):
            chunk_path = input_file.with_suffix(f"{input_file.suffix}.{i+1:03d}")
            bytes_in_chunk = 0
            with open(chunk_path, "wb") as out:
                while bytes_in_chunk < chunk_size:
                    to_read = min(READ_BUFFER, chunk_size - bytes_in_chunk)
                    data = f.read(to_read)
                    if not data:
                        break
                    out.write(data)
                    bytes_in_chunk += len(data)
                    bytes_written_total += len(data)
                    if on_progress:
                        on_progress(bytes_written_total, file_size)
            output_files.append(chunk_path)

    return output_files


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------
def run_gui():
    import tkinter as tk
    from tkinter import filedialog, ttk

    root = tk.Tk()
    root.title("TLEX — File Splitter")
    root.configure(bg="#18181b")
    root.resizable(False, False)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TLabel", background="#18181b", foreground="#fafafa", font=("Segoe UI", 10))
    style.configure("TButton", font=("Segoe UI", 10))
    style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"), foreground="#e5a00d")
    style.configure("Sub.TLabel", foreground="#a1a1aa", font=("Segoe UI", 9))
    style.configure("green.Horizontal.TProgressbar", troughcolor="#27272a", background="#22c55e")

    files: list[str] = []

    # --- Header ---
    ttk.Label(root, text="File Splitter", style="Header.TLabel").pack(pady=(16, 4))
    ttk.Label(root, text="Splitta file grandi per Telegram", style="Sub.TLabel").pack()

    # --- File list ---
    frame = tk.Frame(root, bg="#18181b")
    frame.pack(padx=20, pady=(16, 8), fill="x")

    listbox = tk.Listbox(
        frame, height=6, width=60,
        bg="#27272a", fg="#fafafa", selectbackground="#e5a00d",
        font=("Segoe UI", 9), borderwidth=0, highlightthickness=1,
        highlightcolor="#3f3f46", highlightbackground="#27272a",
    )
    listbox.pack(fill="x")

    btn_frame = tk.Frame(root, bg="#18181b")
    btn_frame.pack(padx=20, fill="x")

    def add_files():
        paths = filedialog.askopenfilenames(
            title="Seleziona file da splittare",
            filetypes=[("Video", "*.mkv *.mp4 *.avi *.webm"), ("Tutti", "*.*")],
        )
        for p in paths:
            if p not in files:
                files.append(p)
                name = Path(p).name
                size_gb = Path(p).stat().st_size / (1024 ** 3)
                listbox.insert(tk.END, f"{name}  ({size_gb:.2f} GB)")

    def remove_selected():
        sel = listbox.curselection()
        for i in reversed(sel):
            files.pop(i)
            listbox.delete(i)

    ttk.Button(btn_frame, text="Aggiungi file", command=add_files).pack(side="left", pady=4)
    ttk.Button(btn_frame, text="Rimuovi", command=remove_selected).pack(side="left", padx=(8, 0), pady=4)

    # --- Chunk size ---
    size_frame = tk.Frame(root, bg="#18181b")
    size_frame.pack(padx=20, pady=(12, 4), fill="x")

    ttk.Label(size_frame, text="Dimensione chunk (MB):").pack(side="left")
    chunk_var = tk.StringVar(value=str(DEFAULT_CHUNK_MB))
    chunk_entry = tk.Entry(
        size_frame, textvariable=chunk_var, width=8,
        bg="#27272a", fg="#fafafa", insertbackground="#fafafa",
        font=("Segoe UI", 10), borderwidth=0,
    )
    chunk_entry.pack(side="left", padx=(8, 0))
    ttk.Label(size_frame, text="(3900 = Premium, 1900 = Free)", style="Sub.TLabel").pack(side="left", padx=(8, 0))

    # --- Progress ---
    progress_var = tk.DoubleVar(value=0)
    status_var = tk.StringVar(value="Pronto")

    ttk.Label(root, textvariable=status_var, style="Sub.TLabel").pack(padx=20, pady=(12, 2), anchor="w")
    progress_bar = ttk.Progressbar(
        root, variable=progress_var, maximum=100,
        style="green.Horizontal.TProgressbar", length=400,
    )
    progress_bar.pack(padx=20, fill="x")

    # --- Start ---
    def start_split():
        if not files:
            status_var.set("Nessun file selezionato")
            return

        try:
            chunk_mb = int(chunk_var.get())
        except ValueError:
            status_var.set("Dimensione chunk non valida")
            return

        chunk_bytes = chunk_mb * 1024 * 1024
        start_btn.config(state="disabled")

        def worker():
            total_files = len(files)
            for idx, fpath in enumerate(files, 1):
                name = Path(fpath).name
                status_var.set(f"[{idx}/{total_files}] Splitting {name}...")

                def on_progress(written, total):
                    pct = (written / total) * 100 if total else 0
                    progress_var.set(pct)

                try:
                    split_file(fpath, chunk_bytes, on_progress=on_progress)
                except Exception as e:
                    status_var.set(f"Errore: {e}")
                    start_btn.config(state="normal")
                    return

            progress_var.set(100)
            status_var.set(f"Completato! {total_files} file splittati")
            start_btn.config(state="normal")

        threading.Thread(target=worker, daemon=True).start()

    start_btn = ttk.Button(root, text="Splitta", command=start_split)
    start_btn.pack(pady=(16, 20))

    # Center window
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"+{x}+{y}")

    root.mainloop()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def run_cli(file_paths: list[str], chunk_mb: int):
    chunk_bytes = chunk_mb * 1024 * 1024
    for i, fpath in enumerate(file_paths, 1):
        p = Path(fpath)
        size_gb = p.stat().st_size / (1024 ** 3)
        num_chunks = (p.stat().st_size + chunk_bytes - 1) // chunk_bytes
        print(f"\n[{i}/{len(file_paths)}] {p.name}  ({size_gb:.2f} GB) -> {num_chunks} parti")

        results = split_file(fpath, chunk_bytes)
        for r in results:
            print(f"  -> {r.name}")

    print(f"\nCompletato! {len(file_paths)} file splittati.")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    chunk_flag = DEFAULT_CHUNK_MB
    if "--chunk-mb" in sys.argv:
        idx = sys.argv.index("--chunk-mb")
        if idx + 1 < len(sys.argv):
            chunk_flag = int(sys.argv[idx + 1])

    if not args:
        run_gui()
    else:
        run_cli(args, chunk_flag)
