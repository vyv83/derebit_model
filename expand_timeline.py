import gzip
import requests
import os
import calendar
import time
from datetime import datetime, timedelta

ARCHIVE_DIR = os.path.join(os.getcwd(), "archives_all_years")
os.makedirs(ARCHIVE_DIR, exist_ok=True)

def get_last_friday(year, month):
    # The last day of the month
    last_day = calendar.monthrange(year, month)[1]
    d = datetime(year, month, last_day)
    # 4 is Friday
    while d.weekday() != 4:
        d -= timedelta(days=1)
    return d

def generate_cd_maturity_links():
    links = []
    months_abbr = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    
    # Try 2021 to 2025
    for y in range(21, 26):
        for m_idx, m_name in enumerate(months_abbr, 1):
            date_obj = get_last_friday(2000 + y, m_idx)
            maturity_str = f"{date_obj.day}{m_name}{y}"
            # DeriBit_BTC_26MAY23_allStrikes_aggregated.zip
            url = f"https://www.cryptodatadownload.com/cdd/DeriBit_BTC_{maturity_str}_allStrikes_aggregated.zip"
            links.append((maturity_str, url))
    return links

def generate_tardis_sample_links():
    links = []
    for year in range(2021, 2026):
        for month in range(1, 13):
            if year == 2025 and month > datetime.now().month:
                continue
            date_str = f"{year}-{month:02d}-01"
            # Tardis format
            # https://datasets.tardis.dev/v1/deribit/options_chain/2024/01/01/OPTIONS.csv.gz
            url = f"https://datasets.tardis.dev/v1/deribit/options_chain/{year}/{month:02d}/01/OPTIONS.csv.gz"
            links.append((date_str, url))
    return links

def download_file(url, save_name, logger=None, stop_signal=None, context_date="-", api_key=None):
    path = os.path.join(ARCHIVE_DIR, save_name)
    
    def log(msg):
        if logger: logger(msg)
        else: print(msg)

    # Check existing size for resume
    existing_size = os.path.getsize(path) if os.path.exists(path) else 0
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    if existing_size > 0:
        headers['Range'] = f'bytes={existing_size}-'
        log(f"  ↪ Resuming {save_name} from {existing_size/1024/1024:.1f} MB...")
    
    if api_key:
        headers['Authorization'] = f"Bearer {api_key}"

    try:
        r = requests.get(url, headers=headers, stream=True, timeout=60)
        
        if r.status_code == 403:
            log(f"  ⚠️ Access Forbidden (403) for {save_name}. Possible rate limit or block.")
            return False
        
        # Total size for progress calculation
        total_size = int(r.headers.get('content-length', 0)) + existing_size
        
        # If server returns 416 (Requested Range Not Satisfiable), file is complete
        if r.status_code == 416:
            log(f"PROGRESS:{context_date}|Finalizing|100|0.0 MB/s|{save_name}")
            log(f"  ✅ {save_name} is already complete.")
            return True
            
        if r.status_code not in [200, 206]:
            log(f"  ❌ Server returned {r.status_code} for {save_name}")
            return False

        mode = 'wb'
        if r.status_code == 200 and existing_size > 0:
            # Maybe it's already full? Check integrity before wiping.
            try:
                with gzip.open(path, 'rb') as f_test:
                    f_test.seek(-1, 2)
                    f_test.read(1)
                log(f"PROGRESS:{context_date}|Existing|100|0.0 MB/s|{save_name}")
                log(f"  ✨ Local file {save_name} is already complete. Skipping download.")
                return True
            except:
                log(f"  ⚠️ Server doesn't support resume, restarting {save_name}...")
                existing_size = 0
        elif r.status_code == 206:
            mode = 'ab'

        accumulated = 0
        last_log_time = time.time()
        last_accumulated = 0

        with open(path, mode) as f:
            for chunk in r.iter_content(chunk_size=1024*1024): # 1MB chunks
                if chunk:
                    if stop_signal and stop_signal():
                        log("  🛑 Download interrupted by user.")
                        raise InterruptedError("Stopped")
                        
                    f.write(chunk)
                    accumulated += len(chunk)
                    
                    now = time.time()
                    if now - last_log_time >= 0.5:
                        speed = (accumulated - last_accumulated) / (now - last_log_time) / (1024*1024)
                        current_total = existing_size + accumulated
                        
                        # Accurate percentage if total_size is known, else heuristic
                        if total_size > 0:
                            pct = min(100, (current_total / total_size) * 100)
                            total_final_mb = total_size / (1024*1024)
                        else:
                            pct = min(99, (current_total / 1_500_000_000) * 100)
                            total_final_mb = 0
                        
                        curr_mb = current_total / (1024*1024)
                        log(f"PROGRESS:{context_date}|Downloading|{pct:.1f}|{speed:.2f} MB/s|{save_name}|{curr_mb:.1f}|{total_final_mb:.1f}")
                        
                        last_log_time = now
                        last_accumulated = accumulated
        
        # Double check: if we have total_size, did we actually reach it?
        final_size = os.path.getsize(path)
        if total_size > 0 and final_size < total_size:
            log(f"  ⚠️ Connection closed prematurely ({final_size}/{total_size} bytes).")
            return False
            
        # Final safety check: try to read the last byte of GZ to ensure it's not truncated
        try:
            with gzip.open(path, 'rb') as f:
                f.seek(-1, 2)
                f.read(1)
        except Exception as e:
            log(f"  ❌ GZIP Integrity Check Failed: File is likely truncated or corrupted. ({str(e)})")
            return False
        
        log(f"PROGRESS:{context_date}|Finalizing|100|0.0 MB/s|{save_name}")
        log(f"  ✅ Finished: {save_name} (Total: {final_size/1e6:.1f} MB)")
        return True
    except Exception as e:
        log(f"  ⚠️ Error downloading {save_name}: {str(e)}")
        return False

def run_collection():
    print("--- Phase 1: Monthly Maturity Archives (CDD) ---")
    cdd_links = generate_cd_maturity_links()
    found_cdd = 0
    for mat, url in cdd_links:
        if download_file(url, f"CDD_Maturity_{mat}.zip"):
            found_cdd += 1
            
    print(f"\nFound {found_cdd} full-strike archives from CDD.")

    print("\n--- Phase 2: Monthly Full-Chain Snapshots (Tardis) ---")
    tardis_links = generate_tardis_sample_links()
    found_tardis = 0
    for date_str, url in tardis_links:
        print(f"Checking {date_str}...")
        if download_file(url, f"TARDIS_Snap_{date_str}.csv.gz"):
            found_tardis += 1
            
    print(f"\nFound {found_tardis} monthly snapshots from Tardis.")

if __name__ == "__main__":
    run_collection()
