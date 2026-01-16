"""
ML Package
==========
Machine learning models for options pricing and Greeks prediction.

This package contains:
- model_architecture.py: Neural network architecture (ImprovedMultiTaskSVI)
- model_wrapper.py: OptionModel wrapper for predictions

Example:
--------
>>> from ml import OptionModel
>>> model = OptionModel('best_multitask_svi.pth')
>>> predictions = model.predict(market_state, strikes, dte_days)
"""

from .model_wrapper import OptionModel

__all__ = ['OptionModel']
