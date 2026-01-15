"""
Option Timeseries Provider
==========================
Generates on-the-fly OHLC candlestick data for individual option contracts
from historical parquet snapshots.
"""

import pandas as pd
import numpy as np
import os
import glob
from datetime import datetime, timedelta
from typing import Optional, Tuple


class OptionTimeseriesProvider:
    """
    Provides timeseries data for option contracts by reading from 
    processed parquet files.
    """
    
    def __init__(self, data_dir='processed_snapshots'):
        """
        Initialize the provider.
        
        Args:
            data_dir: Directory containing processed parquet files
        """
        self.data_dir = data_dir
        if not os.path.isabs(data_dir):
            # Make relative to the model directory
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.data_dir = os.path.join(os.path.dirname(base_dir), data_dir)
    
    def _build_symbol(self, strike: float, exp_date: str, option_type: str) -> str:
        """
        Constructs Deribit symbol from components.
        
        Args:
            strike: Strike price (e.g., 50000)
            exp_date: Expiration date string (e.g., '2024-09-27')
            option_type: 'call' or 'put'
        
        Returns:
            Symbol like 'BTC-27SEP24-50000-C'
        """
        exp_dt = pd.to_datetime(exp_date)
        day = exp_dt.strftime('%d')
        month = exp_dt.strftime('%b').upper()
        year = exp_dt.strftime('%y')
        
        type_code = 'C' if option_type.lower() == 'call' else 'P'
        strike_int = int(strike)
        
        # Currency is determined from context, will be passed separately
        return f"{day}{month}{year}-{strike_int}-{type_code}"
    
    def get_option_ohlc_data(
        self, 
        currency: str,
        strike: float, 
        exp_date: str,
        option_type: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Generates OHLC candlestick data for a specific option contract.
        
        Args:
            currency: 'BTC' or 'ETH'
            strike: Strike price
            exp_date: Expiration date (YYYY-MM-DD format)
            option_type: 'call' or 'put'
            start_date: Start of time range (YYYY-MM-DD)
            end_date: End of time range (YYYY-MM-DD)
        
        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume]
            Empty DataFrame if no data found
        """
        try:
            # Build the full symbol
            symbol_suffix = self._build_symbol(strike, exp_date, option_type)
            symbol = f"{currency}-{symbol_suffix}"
            
            # Parse dates
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            # Determine which parquet files to load
            files_to_load = self._get_relevant_files(currency, start_dt, end_dt)
            
            if not files_to_load:
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Load and filter data
            all_data = []
            for filepath in files_to_load:
                try:
                    df = pd.read_parquet(filepath)
                    # Filter by symbol and time range
                    mask = (
                        (df['symbol'] == symbol) &
                        (df['snapshot_time'] >= start_dt) &
                        (df['snapshot_time'] <= end_dt)
                    )
                    filtered = df[mask]
                    if not filtered.empty:
                        all_data.append(filtered)
                except Exception as e:
                    print(f"Warning: Could not load {filepath}: {e}")
                    continue
            
            if not all_data:
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Combine all data
            combined = pd.concat(all_data, ignore_index=True)
            combined = combined.sort_values('snapshot_time')
            
            # Build OHLC candlesticks
            # Each row in the parquet is already a snapshot, so we use mark_price as OHLC
            # For more granular data, we'd need intraday updates
            ohlc_data = []
            for _, row in combined.iterrows():
                # Use mark_price as the candle value
                # Since we have hourly snapshots, each snapshot becomes one candle
                price = row.get('mark_price', row.get('last_price', 0))
                if pd.isna(price) or price == 0:
                    continue
                    
                ohlc_data.append({
                    'timestamp': row['snapshot_time'],
                    'open': price,
                    'high': price,
                    'low': price,
                    'close': price,
                    'volume': row.get('open_interest', 0)
                })
            
            if not ohlc_data:
                return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            result_df = pd.DataFrame(ohlc_data)
            return result_df
            
        except Exception as e:
            print(f"Error generating OHLC data: {e}")
            import traceback
            traceback.print_exc()
            return pd.DataFrame(columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    
    def get_base_asset_prices(
        self,
        currency: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Extracts base asset (BTC/ETH) prices over time range.
        
        Args:
            currency: 'BTC' or 'ETH'
            start_date: Start of time range (YYYY-MM-DD)
            end_date: End of time range (YYYY-MM-DD)
        
        Returns:
            DataFrame with columns: [timestamp, price]
        """
        try:
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            
            files_to_load = self._get_relevant_files(currency, start_dt, end_dt)
            
            if not files_to_load:
                return pd.DataFrame(columns=['timestamp', 'price'])
            
            all_prices = []
            for filepath in files_to_load:
                try:
                    df = pd.read_parquet(filepath)
                    # Filter by time
                    mask = (df['snapshot_time'] >= start_dt) & (df['snapshot_time'] <= end_dt)
                    filtered = df[mask]
                    
                    if not filtered.empty:
                        # Extract unique timestamps and their underlying prices
                        price_data = filtered[['snapshot_time', 'underlying_price']].drop_duplicates('snapshot_time')
                        all_prices.append(price_data)
                except Exception as e:
                    print(f"Warning: Could not load {filepath}: {e}")
                    continue
            
            if not all_prices:
                return pd.DataFrame(columns=['timestamp', 'price'])
            
            combined = pd.concat(all_prices, ignore_index=True)
            combined = combined.drop_duplicates('snapshot_time').sort_values('snapshot_time')
            combined = combined.rename(columns={'snapshot_time': 'timestamp', 'underlying_price': 'price'})
            
            return combined[['timestamp', 'price']]
            
        except Exception as e:
            print(f"Error getting base asset prices: {e}")
            return pd.DataFrame(columns=['timestamp', 'price'])
    
    def _get_relevant_files(self, currency: str, start_dt: datetime, end_dt: datetime) -> list:
        """
        Determines which parquet files cover the requested time range.
        
        Args:
            currency: 'BTC' or 'ETH'
            start_dt: Start datetime
            end_dt: End datetime
        
        Returns:
            List of absolute file paths
        """
        files = []
        
        # Generate all year-month combinations in range
        current = start_dt.replace(day=1)
        end_month = end_dt.replace(day=1)
        
        while current <= end_month:
            pattern = f"{currency}_{current.year}-{current.month:02d}.parquet"
            filepath = os.path.join(self.data_dir, pattern)
            
            if os.path.exists(filepath):
                files.append(filepath)
            
            # Move to next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        return files
