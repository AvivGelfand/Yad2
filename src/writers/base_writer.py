from abc import ABC, abstractmethod
from typing import List, Dict, Any
import pandas as pd


class BaseWriter(ABC):
    """Abstract base class for data writers"""
    
    @abstractmethod
    def write(self, data: pd.DataFrame) -> bool:
        """Write data to the target destination"""
        pass
    
    @abstractmethod
    def update(self, data: pd.DataFrame) -> bool:
        """Update existing data in the target destination"""
        pass
    
    @abstractmethod
    def clear(self) -> bool:
        """Clear all data from the target destination"""
        pass