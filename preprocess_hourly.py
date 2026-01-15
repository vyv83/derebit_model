import pandas as pd
import numpy as np
import os
import time
import glob
from datetime import datetime

SOURCE_DIR = "archives_all_years"
OUTPUT_DIR = "processed_snapshots"

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)

def preprocess_month(year, month, logger=None):
    """
    Optimized monthly processing. 
    Uses integer math for time slots to avoid heavy datetime parsing.
    """
    def log(msg, end='\n'):
        if logger:
            logger(f"{msg}{end}")
        else:
            print(msg, end=end)

    pattern = f"TARDIS_Snap_{year}-{month:02d}-*.csv.gz"
    files = sorted(glob.glob(os.path.join(SOURCE_DIR, pattern)))
    
    if not files:
        log(f"❌ No files found for {year}-{month:02d}")
        return
    
    log(f"📂 Found {len(files)} files. Starting optimized processing...")
    
    btc_state, eth_state = {}, {}
    btc_snapshots, eth_snapshots = [], []
    
    cols_to_keep = [
        'snapshot_time', 'symbol', 'type', 'strike_price', 'expiration', 
        'open_interest', 'last_price', 'bid_price', 'bid_iv', 'ask_price', 
        'ask_iv', 'mark_price', 'mark_iv', 'underlying_price', 
        'delta', 'gamma', 'vega', 'theta', 'rho'
    ]

    # One hour in microseconds
    HOUR_US = 3600 * 1_000_000
    last_hour_idx = None

    for filepath in files:
        filename = os.path.basename(filepath)
        log(f"🎬 Reading {filename}...")
        
        # Read in chunks
        chunk_size = 1_000_000 # Larger chunks for efficiency
        reader = pd.read_csv(filepath, compression='gzip', chunksize=chunk_size)
        
        for chunk in reader:
            chunk.columns = [c.lower() for c in chunk.columns]
            
            # Fast currency tag
            chunk['is_btc'] = chunk['symbol'].str.startswith('BTC')
            
            # Fast hour indexing (integers)
            chunk['hour_idx'] = chunk['timestamp'] // HOUR_US
            
            # We iterate through unique hours in this chunk
            unique_hours = chunk['hour_idx'].unique()
            
            for h_idx in unique_hours:
                if last_hour_idx is not None and h_idx != last_hour_idx:
                    # Hour transition! Save current state as a snapshot
                    snap_time = datetime.fromtimestamp((last_hour_idx * HOUR_US) / 1_000_000)
                    
                    if btc_state:
                        df_btc = pd.DataFrame(btc_state.values())
                        df_btc['snapshot_time'] = snap_time
                        btc_snapshots.append(df_btc[[c for c in cols_to_keep if c in df_btc.columns]])
                    
                    if eth_state:
                        df_eth = pd.DataFrame(eth_state.values())
                        df_eth['snapshot_time'] = snap_time
                        eth_snapshots.append(df_eth[[c for c in cols_to_keep if c in df_eth.columns]])
                    
                    log(f"  📌 Snapshot: {snap_time.strftime('%Y-%m-%d %H:%M')}", end='\r')

                # Update states with the latest data for this hour in this chunk
                hour_data = chunk[chunk['hour_idx'] == h_idx]
                # Efficient update: get last occurrences per symbol
                updates = hour_data.sort_values('timestamp').drop_duplicates('symbol', keep='last')
                
                # Split and update
                for _, row in updates.iterrows():
                    sym = row['symbol']
                    r_dict = row.to_dict()
                    if row['is_btc']:
                        btc_state[sym] = r_dict
                    else:
                        eth_state[sym] = r_dict
                
                last_hour_idx = h_idx
            
    # Final cleanup and save
    if btc_snapshots:
        out_btc = os.path.join(OUTPUT_DIR, f"BTC_{year}-{month:02d}.parquet")
        pd.concat(btc_snapshots, ignore_index=True).to_parquet(out_btc, compression='snappy')
        log(f"\n✅ Created {out_btc}")
    
    if eth_snapshots:
        out_eth = os.path.join(OUTPUT_DIR, f"ETH_{year}-{month:02d}.parquet")
        pd.concat(eth_snapshots, ignore_index=True).to_parquet(out_eth, compression='snappy')
        log(f"✅ Created {out_eth}")

if __name__ == "__main__":
    # Test for Feb 2021
    preprocess_month(2021, 2)
