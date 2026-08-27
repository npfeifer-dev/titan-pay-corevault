import pandas as pd
import numpy as np

def calculate_merchant_exposure(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates daily settlement exposure and flags concentration risk."""
    exposure_df = df.groupby('merchant_id').agg(
        total_volume=('transaction_amount', 'sum'),
        transaction_count=('transaction_id', 'count'),
        avg_ticket=('transaction_amount', 'mean')
    ).reset_index()
    
    total_system_volume = exposure_df['total_volume'].sum()
    exposure_df['concentration_pct'] = (exposure_df['total_volume'] / total_system_volume) * 100
    exposure_df['risk_flag'] = np.where(exposure_df['concentration_pct'] > 10.0, 'HIGH_EXPOSURE', 'NORMAL')
    
    return exposure_df

def detect_refund_anomalies(df: pd.DataFrame, refund_threshold: float = 0.05) -> pd.DataFrame:
    """Flags merchants exceeding safe refund volume ratios."""
    metrics = df.groupby('merchant_id').agg(
        gross_sales=('transaction_amount', lambda x: x[x > 0].sum()),
        refunds=('transaction_amount', lambda x: abs(x[x < 0].sum()))
    ).reset_index()
    
    metrics['refund_ratio'] = metrics['refunds'] / metrics['gross_sales']
    metrics['leakage_alert'] = metrics['refund_ratio'] > refund_threshold
    
    return metrics[metrics['leakage_alert']]
