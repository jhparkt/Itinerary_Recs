import argparse, os, sys, time, requests, zipfile

CHUNK = 1024 * 64  # 64 KiB
DEFAULT_URL = "https://www.sdmts.com/google_transit_files/google_transit.zip"

CORE_GTFS_FILES = {
    "agency.txt", "stops.txt", "routes.txt",
    "trips.txt", "stop_times.txt", "calendar.txt", "calendar_dates.txt"
}

def expand(p: str) -> str:
    return os.path.abspath(os.path.expanduser(p))

def ensure_dir(path: str):
    """Create directory if it doesn't exist and ensure it's writable."""
    path = expand(path)
    os.makedirs(path, exist_ok=True)
    testfile = os.path.join(path, ".write_test")
    with open(testfile, "w") as f:
        f.write("ok")
    os.remove(testfile)
    return path

def human(n: int) -> str:
    for unit in ("B","KB","MB","GB","TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"

def download_zip(url: str, outdir: str, timeout: int = 180) -> str:
    outdir = ensure_dir(outdir)
    zip_path = os.path.join(outdir, "gtfs_latest.zip")

    print(f"[download] GET {url}")
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        total = r.headers.get("Content-Length")
        total_int = int(total) if total and total.isdigit() else None

        bytes_so_far = 0
        start = time.perf_counter()
        with open(zip_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=CHUNK):
                if chunk:
                    f.write(chunk)
                    bytes_so_far += len(chunk)
                    if total_int:
                        pct = (bytes_so_far / total_int) * 100
                        speed = bytes_so_far / max(1e-6, (time.perf_counter() - start))
                        sys.stdout.write(
                            f"\r[progress] {pct:6.2f}% {human(bytes_so_far):>9} / {human(total_int):<9} "
                            f"@ {human(int(speed))}/s"
                        )
                        sys.stdout.flush()
        if total_int:
            sys.stdout.write("\n")
    print(f"[save] ZIP saved --> {zip_path}")
    return zip_path

def extract_zip(zip_path: str, extract_dir: str):
    """Extract directly into ./raw_data/gtfs (no subfolder)."""
    print(f"[extract] Unzipping to {extract_dir}")
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(extract_dir)
    extracted = os.listdir(extract_dir)
    print(f"[extract] Extracted {len(extracted)} files:")
    for f in sorted(extracted):
        print("  -", f)

def verify(extract_dir: str):
    """Check that the required GTFS text files exist."""
    files = set(os.listdir(extract_dir))
    missing = [f for f in CORE_GTFS_FILES if f not in files]
    if missing:
        print("[verify] ⚠ Missing files:")
        for m in missing:
            print("  -", m)
    else:
        print("[verify] ✓ All core GTFS files present")

def main():
    ap = argparse.ArgumentParser(description="Download & extract San Diego MTS GTFS feed directly into ./raw_data/gtfs/")
    ap.add_argument("--url", default=DEFAULT_URL, help="GTFS ZIP URL")
    ap.add_argument("--outdir", default="./raw_data/gtfs", help="Output folder (unzipped files go here)")
    ap.add_argument("--timeout", type=int, default=180, help="HTTP timeout seconds")
    ap.add_argument("--keep_zip", action="store_true", help="Keep the ZIP file (default: delete it after extraction)")
    args = ap.parse_args()

    outdir = ensure_dir(args.outdir)
    try:
        zip_path = download_zip(args.url, outdir, timeout=args.timeout)
        extract_zip(zip_path, outdir)
        verify(outdir)

        if not args.keep_zip:
            os.remove(zip_path)
            print(f"[cleanup] Deleted ZIP: {zip_path}")

        print(f"[done] ✅ GTFS feed ready in: {outdir}")
    except Exception as e:
        print(f"[error] {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()