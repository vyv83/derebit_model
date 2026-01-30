import pandas as pd
import numpy as np
from datetime import datetime

class DailyFeatureProvider:
    def __init__(self, price_file='btc_full_history.csv', dvol_file='btc_dvol_history.csv'):
        self.price_file = price_file
        self.dvol_file = dvol_file
        self.df_merged = None
        self._load_data()
        
    def _load_data(self):
        print("Loading CSV history...")
        # Load Price
        df_price = pd.read_csv(self.price_file, parse_dates=['Date'])
        df_price.set_index('Date', inplace=True)
        df_price.sort_index(inplace=True)
        
        # Load Vol
        df_vol = pd.read_csv(self.dvol_file, parse_dates=['Date'])
        df_vol.set_index('Date', inplace=True)
        # Rename DVOL_Close to Real_IV_ATM (DVOL is approx ATM IV)
        df_vol.rename(columns={'DVOL_Close': 'Real_IV_ATM'}, inplace=True)
        # DVOL is index (e.g. 50), model expects ratio (0.50)
        df_vol['Real_IV_ATM'] = df_vol['Real_IV_ATM'] / 100.0
        
        # Merge
        self.df_merged = df_price.join(df_vol, how='inner') # We generally need both
        
        # Feature Engineering
        self._compute_features()
        print(f"Loaded {len(self.df_merged)} daily records from {self.df_merged.index.min().date()} to {self.df_merged.index.max().date()}")

    def _compute_features(self):
        df = self.df_merged
        
        # Returns
        df['Returns'] = df['Close'].pct_change()
        df['Log_Returns'] = np.log(df['Close'] / df['Close'].shift(1))
        
        # Rolling Features (30 Days)
        window = 30
        df['HV_30d'] = df['Log_Returns'].rolling(window).std() * np.sqrt(365)
        df['Skew_30d'] = df['Returns'].rolling(window).skew()
        df['Kurt_30d'] = df['Returns'].rolling(window).kurt()
        df['Cum_Returns_30d'] = df['Returns'].rolling(window).sum()
        
        # Drawdown
        df['Running_Max'] = df['Close'].expanding().max()
        df['Drawdown'] = (df['Close'] - df['Running_Max']) / df['Running_Max']
        
        # Vol Spike & Ratio
        # IV/HV Ratio
        # Avoid div by zero
        df['IV_HV_Ratio'] = df['Real_IV_ATM'] / df['HV_30d'].replace(0, np.nan)
        
        # Vol Spike
        iv_recent = df['Real_IV_ATM'].rolling(7).mean()
        iv_long = df['Real_IV_ATM'].rolling(60).mean()
        df['Vol_Spike'] = (iv_recent - iv_long) / iv_long
        
        # Temporal
        df['Month'] = df.index.month
        df['Quarter'] = df.index.quarter
        df['DayOfWeek'] = df.index.dayofweek
        
        # Fill/Drop
        # Forward fill some gaps if any, but inner join handled most
        self.df_merged = df.ffill().dropna()

    def get_market_state(self, target_date):
        # target_date can be string or datetime
        ts = pd.to_datetime(target_date)
        
        # Find closest date (method='nearest') or exact
        try:
            # We use asof to get the latest available data up to that point
            idx = self.df_merged.index.get_indexer([ts], method='pad')[0]
            if idx == -1: return None
            
            row = self.df_merged.iloc[idx]
            
            # Map columns to model expected names
            state = {
                'underlying_price': row['Close'],
                'Real_IV_ATM': row['Real_IV_ATM'],
                'HV_30d': row['HV_30d'],
                'IV_HV_Ratio': row['IV_HV_Ratio'],
                'Skew_30d': row['Skew_30d'],
                'Kurt_30d': row['Kurt_30d'],
                'Drawdown': row['Drawdown'],
                'Vol_Spike': row['Vol_Spike'],
                'Cum_Returns_30d': row['Cum_Returns_30d'],
                'Month': int(row['Month']),
                'Quarter': int(row['Quarter']),
                'DayOfWeek': int(row['DayOfWeek']),
                'target_ts': str(self.df_merged.index[idx])
            }
            return state
        except Exception as e:
            print(f"Error getting state for {target_date}: {e}")
            return None

    def get_date_range(self):
        return self.df_merged.index

    def get_high_low(self, start_date, end_date):
        """Returns (min_price, max_price) for the given period."""
        try:
            mask = (self.df_merged.index >= pd.to_datetime(start_date)) & (self.df_merged.index <= pd.to_datetime(end_date))
            subset = self.df_merged.loc[mask]
            if subset.empty:
                return None, None
            return subset['Close'].min(), subset['Close'].max()
        except Exception:
            return None, None

