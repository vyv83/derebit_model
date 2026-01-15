import os
import json
import time
import pandas as pd
from datetime import datetime, timedelta
from expand_timeline import download_file

STATE_FILE = "harvest_state.json"
MARKET_STATE_PKL = "market_state.pkl"
STAGING_DIR = "staging"
PROCESSED_DIR = "processed_snapshots"

import pickle

class DataHarvester:
    def __init__(self, logger=None):
        self.logger = logger
        self.state = self.load_state()
        self.market_state = self.load_market_state()
        self.space_saved_bytes = self.state.get("space_saved", 0)
        
        # Ensure directories exist
        os.makedirs(STAGING_DIR, exist_ok=True)
        os.makedirs(PROCESSED_DIR, exist_ok=True)
        os.makedirs("archives_all_years", exist_ok=True)

    def log(self, msg):
        if self.logger: self.logger(msg)
        else: print(msg)

    def load_state(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        return {"processed_days": [], "space_saved": 0}

    def load_market_state(self):
        if os.path.exists(MARKET_STATE_PKL):
            with open(MARKET_STATE_PKL, 'rb') as f:
                return pickle.load(f)
        return {"BTC": {}, "ETH": {}}

    def save_market_state(self):
        with open(MARKET_STATE_PKL, 'wb') as f:
            pickle.dump(self.market_state, f)

    def save_state(self):
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f)

    def get_date_range(self, start_date_str="2021-01-01"):
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.now() - timedelta(days=1)
        
        dates = []
        curr = start_date
        while curr <= end_date:
            dates.append(curr.strftime("%Y-%m-%d"))
            curr += timedelta(days=1)
        return dates

    def run(self):
        target_dates = self.get_date_range()
        self.log(f"🚀 Starting Auto-Harvest. Target: {len(target_dates)} days.")

        for date_str in target_dates:
            if date_str in self.state["processed_days"]:
                continue
            
            # 1. Check if month is already finalized
            year_month = date_str[:7] # YYYY-MM
            if os.path.exists(os.path.join(PROCESSED_DIR, f"BTC_{year_month}.parquet")):
                 # If finalized file exists, mark all days of this month as done
                 self.log(f"⏭ Month {year_month} already finalized. Skipping.")
                 self.mark_month_done(year_month)
                 continue

            self.log(f"--- Processing Day: {date_str} ---")
            
            # 2. Download with Retry
            url = f"https://datasets.tardis.dev/v1/deribit/options_chain/{date_str.replace('-','/')}/OPTIONS.csv.gz"
            save_name = f"TARDIS_Snap_{date_str}.csv.gz"
            
            success = False
            for attempt in range(3):
                if download_file(url, save_name, logger=self.logger):
                    success = True
                    break
                self.log(f"⚠️ Retry {attempt+1}/3 in 10s...")
                time.sleep(10)

            if not success:
                self.log(f"❌ Failed to download {date_str} after retries. Stopping.")
                break
            
            # 3. Process (Daily)
            try:
                gz_path = os.path.join("archives_all_years", save_name)
                gz_size = os.path.getsize(gz_path)
                
                self.process_daily_file(save_name, date_str)
                
                # 4. Cleanup GZ & Track Savings
                if os.path.exists(gz_path):
                    os.remove(gz_path)
                    self.space_saved_bytes += gz_size
                    self.log(f"🗑 Deleted {save_name}. Total space saved: {self.space_saved_bytes/1e9:.2f} GB")
                
                self.state["processed_days"].append(date_str)
                self.state["space_saved"] = self.space_saved_bytes
                self.save_state()
                self.save_market_state()
                
            except Exception as e:
                self.log(f"💥 Error processing {date_str}: {e}")
                break

    def mark_month_done(self, year_month):
        # Fill state for all days of the month to avoid re-checking
        y, m = map(int, year_month.split("-"))
        import calendar
        _, last_day = calendar.monthrange(y, m)
        for d in range(1, last_day + 1):
            d_str = f"{y}-{m:02d}-{d:02d}"
            if d_str not in self.state["processed_days"]:
                self.state["processed_days"].append(d_str)
        self.save_state()

    def process_daily_file(self, filename, date_str, stop_signal=None):
        gz_path = os.path.join("archives_all_years", filename)
        btc_snapshots, eth_snapshots = [], []
        
        # Continuity: self.market_state already contains the end of the previous day!
        # This is the secret of 10/10 data quality.
        
        HOUR_US = 3600 * 1_000_000
        last_hour_idx = None
        
        reader = pd.read_csv(gz_path, compression='gzip', chunksize=1_000_000)
        cols_to_keep = [
            'snapshot_time', 'symbol', 'type', 'strike_price', 'expiration', 
            'open_interest', 'last_price', 'bid_price', 'bid_iv', 'ask_price', 
            'ask_iv', 'mark_price', 'mark_iv', 'underlying_price', 
            'delta', 'gamma', 'vega', 'theta', 'rho'
        ]

        chunk_count = 0
        total_rows_processed = 0
        start_t = time.time()
        for chunk in reader:
            if stop_signal and stop_signal():
                self.log(f"  🛑 {date_str}: Processing interrupted by user.")
                raise InterruptedError("Stopped")

            chunk_count += 1
            total_rows_processed += len(chunk)
            
            # Structured Progress Update
            elapsed = time.time() - start_t
            rows_per_sec = total_rows_processed / elapsed if elapsed > 0 else 0
            pct = min(99.0, (chunk_count / 30) * 100) 
            
            # File size info for UI consistency
            file_size_mb = os.path.getsize(gz_path) / (1024*1024)
            proc_mb = (pct/100.0) * file_size_mb

            self.log(f"PROGRESS:{date_str}|Parsing CSV|{pct:.1f}|{rows_per_sec/1000:.1f}k r/s|{filename}|{proc_mb:.1f}|{file_size_mb:.1f}")
            chunk.columns = [c.lower() for c in chunk.columns]
            chunk['is_btc'] = chunk['symbol'].str.startswith('BTC')
            chunk['hour_idx'] = chunk['timestamp'] // HOUR_US
            
            for h_idx in chunk['hour_idx'].unique():
                if last_hour_idx is not None and h_idx != last_hour_idx:
                    snap_time = datetime.fromtimestamp((last_hour_idx * HOUR_US) / 1_000_000)
                    snap_ts_us = last_hour_idx * HOUR_US
                    
                    for coin in ['BTC', 'ETH']:
                        state_dict = self.market_state[coin]
                        if state_dict:
                            # CRITICAL: Prune expired instruments BEFORE creating snapshot
                            # Deribit 'expiration' is in microseconds US
                            expired_keys = [s for s, data in state_dict.items() if data.get('expiration', 0) < snap_ts_us]
                            for k in expired_keys:
                                del state_dict[k]
                            
                            if state_dict:
                                df_snap = pd.DataFrame(state_dict.values())
                                df_snap['snapshot_time'] = snap_time
                                target_list = btc_snapshots if coin == 'BTC' else eth_snapshots
                                target_list.append(df_snap[[c for c in cols_to_keep if c in df_snap.columns]])
                
                # Update MARKET STATE
                hour_data = chunk[chunk['hour_idx'] == h_idx]
                updates = hour_data.sort_values('timestamp').drop_duplicates('symbol', keep='last')
                for _, row in updates.iterrows():
                    coin = 'BTC' if row['is_btc'] else 'ETH'
                    self.market_state[coin][row['symbol']] = row.to_dict()
                last_hour_idx = h_idx

        # Save to staging
        for coin, snaps in [('BTC', btc_snapshots), ('ETH', eth_snapshots)]:
            if snaps:
                df_day = pd.concat(snaps, ignore_index=True)
                out_path = os.path.join(STAGING_DIR, f"{coin}_{date_str}.snap")
                df_day.to_parquet(out_path, compression='snappy')

    def check_and_consolidate(self, year_month, demo_mode=False):
        """If all days for the month are in staging (or if in demo_mode), merge them."""
        y, m = map(int, year_month.split("-"))
        import calendar
        _, last_day = calendar.monthrange(y, m)
        
        is_today_month = (datetime.now().strftime("%Y-%m") == year_month)
        
        days_to_check = last_day
        if is_today_month:
            days_to_check = datetime.now().day - 1
        
        if not demo_mode and days_to_check < 1: return

        all_present = True
        if not demo_mode:
            for d in range(1, days_to_check + 1):
                if f"{year_month}-{d:02d}" not in self.state["processed_days"]:
                    all_present = False
                    break
        else:
            # In demo mode, we just need the 1st day to be done
            all_present = f"{year_month}-01" in self.state["processed_days"]
        
        if all_present:
            self.log(f"📦 Consolidating Month {year_month}...")
            import glob
            for coin in ['BTC', 'ETH']:
                daily_files = sorted(glob.glob(os.path.join(STAGING_DIR, f"{coin}_{year_month}-*.snap")))
                if daily_files:
                    dfs = [pd.read_parquet(f) for f in daily_files]
                    df_month = pd.concat(dfs, ignore_index=True)
                    out_path = os.path.join(PROCESSED_DIR, f"{coin}_{year_month}.parquet")
                    df_month.to_parquet(out_path, compression='snappy')
                    # Cleanup staging
                    for f in daily_files: os.remove(f)
                    self.log(f"  ✅ Finalized {coin}_{year_month}.parquet")

    def repair_staging(self, demo_mode=False):
        """Scan staging and force consolidation for dates already in processed_state."""
        self.log("🔧 Running maintenance: Checking for orphaned snapshots...")
        import glob
        snaps = glob.glob(os.path.join(STAGING_DIR, "*.snap"))
        if not snaps:
            self.log("✨ Staging is clear. No maintenance needed.")
            return

        months_to_fix = set()
        for s in snaps:
            try:
                # BTC_2021-01-01.snap
                date_part = os.path.basename(s).split("_")[1].replace(".snap", "")
                months_to_fix.add(date_part[:7])
            except: continue
            
        for ym in sorted(list(months_to_fix)):
            self.check_and_consolidate(ym, demo_mode=demo_mode)
        self.log("✅ Maintenance complete.")

if __name__ == "__main__":
    harvester = DataHarvester()
    harvester.run()
