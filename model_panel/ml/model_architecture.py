import torch
import torch.nn as nn

class ResidualBlock(nn.Module):
    """Residual block for better gradient flow"""
    
    def __init__(self, dim, dropout=0.15):
        super(ResidualBlock, self).__init__()
        self.block = nn.Sequential(
            nn.Linear(dim, dim),
            nn.ReLU(),
            nn.BatchNorm1d(dim),
            nn.Dropout(dropout)
        )
    
    def forward(self, x):
        return x + self.block(x)  # Skip connection


class ImprovedMultiTaskSVI(nn.Module):
    """
    Improved Multi-Task Architecture:
    1. Residual connections in backbone
    2. Deeper Gamma head
    3. IV head with priority
    """
    
    def __init__(self, input_dim=14, shared_dims=[512, 256, 128], dropout=0.15):
        super(ImprovedMultiTaskSVI, self).__init__()
        
        # ===== SHARED BACKBONE (with Residual Blocks) =====
        self.input_layer = nn.Sequential(
            nn.Linear(input_dim, shared_dims[0]),
            nn.ReLU(),
            nn.BatchNorm1d(shared_dims[0]),
            nn.Dropout(dropout)
        )
        
        # Residual blocks
        self.res_block1 = ResidualBlock(shared_dims[0], dropout)
        self.res_block2 = ResidualBlock(shared_dims[0], dropout)
        
        # Compression layers
        self.compress1 = nn.Sequential(
            nn.Linear(shared_dims[0], shared_dims[1]),
            nn.ReLU(),
            nn.BatchNorm1d(shared_dims[1]),
            nn.Dropout(dropout)
        )
        
        self.res_block3 = ResidualBlock(shared_dims[1], dropout)
        
        self.compress2 = nn.Sequential(
            nn.Linear(shared_dims[1], shared_dims[2]),
            nn.ReLU(),
            nn.BatchNorm1d(shared_dims[2]),
            nn.Dropout(dropout)
        )
        
        head_dim = shared_dims[-1]  # 128
        
        # ===== IV HEAD =====
        self.iv_head = nn.Sequential(
            nn.Linear(head_dim, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Dropout(dropout * 0.5),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Softplus()
        )
        
        # ===== DELTA HEAD =====
        self.delta_head = nn.Sequential(
            nn.Linear(head_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Tanh()
        )
        
        # ===== GAMMA HEAD =====
        self.gamma_head = nn.Sequential(
            nn.Linear(head_dim, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Dropout(dropout),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.BatchNorm1d(32),
            nn.Dropout(dropout),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1)
        )
        
        # ===== VEGA HEAD =====
        self.vega_head = nn.Sequential(
            nn.Linear(head_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
            nn.Softplus()
        )
    
    def forward(self, x):
        # Shared backbone
        x = self.input_layer(x)
        x = self.res_block1(x)
        x = self.res_block2(x)
        x = self.compress1(x)
        x = self.res_block3(x)
        shared_features = self.compress2(x)
        
        # Task-specific predictions
        iv = self.iv_head(shared_features).squeeze(-1)
        delta = self.delta_head(shared_features).squeeze(-1)
        log_gamma = self.gamma_head(shared_features).squeeze(-1)
        vega = self.vega_head(shared_features).squeeze(-1)
        
        # Stack outputs
        outputs = torch.stack([iv, delta, log_gamma, vega], dim=1)
        
        return outputs
