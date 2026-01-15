import torch
import pandas as pd
import numpy as np
from architecture import ImprovedMultiTaskSVI

class OptionModel:
    def __init__(self, model_path='model/neural_svi_v2_multitask_final.pth'):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        # Load the full package
        print(f"Loading model from {model_path}...")
        package = torch.load(model_path, map_location=self.device, weights_only=False)
        
        # Reconstruct architecture
        arch_params = package['model_architecture']
        # Remove 'class' from params as it's not a kwarg for the constructor
        if 'class' in arch_params: arch_params.pop('class')
        
        self.model = ImprovedMultiTaskSVI(**arch_params).to(self.device)
        self.model.load_state_dict(package['model_state_dict'])
        self.model.eval()
        
        self.scaler = package['scaler_X']
        self.input_features = package['input_features']
        print(f"Model loaded successfully on {self.device}")

    def predict(self, market_state, strikes, dte_days, is_call=True):
        """
        Inference for a batch of strikes
        market_state: dict with rolling features
        """
        data = []
        spot = market_state['underlying_price']
        
        for K in strikes:
            # Create input row
            row = {
                'log_moneyness': np.log(spot / K),
                'dte': dte_days, # Model trained on days, not years
                'is_call': 1.0 if is_call else 0.0,
                'Real_IV_ATM': market_state.get('Real_IV_ATM', 0.5),
                'HV_30d': market_state.get('HV_30d', 0.5),
                'IV_HV_Ratio': market_state.get('IV_HV_Ratio', 1.0),
                'Skew_30d': market_state.get('Skew_30d', 0.0),
                'Kurt_30d': market_state.get('Kurt_30d', 0.0),
                'Drawdown': market_state.get('Drawdown', 0.0),
                'Vol_Spike': market_state.get('Vol_Spike', 0.0),
                'Cum_Returns_30d': market_state.get('Cum_Returns_30d', 0.0),
                'Month': market_state.get('Month', 1),
                'Quarter': market_state.get('Quarter', 1),
                'DayOfWeek': market_state.get('DayOfWeek', 0)
            }
            data.append(row)
            
        df_input = pd.DataFrame(data)
        
        # Ensure correct column order
        df_input = df_input[self.input_features]
        
        # Scale
        X_scaled = self.scaler.transform(df_input)
        X_tensor = torch.FloatTensor(X_scaled).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(X_tensor)
            
        # Outputs: [iv, delta, log_gamma, vega]
        preds = outputs.cpu().numpy()
        
        results = pd.DataFrame({
            'strike': strikes,
            'mark_iv': preds[:, 0] * 100, # IV usually in % in the dashboard
            'delta': preds[:, 1],
            'gamma': np.exp(preds[:, 2]),
            'vega': preds[:, 3]
        })
        
        return results
