import pandas as pd
import duckdb

def load_legacy_ledger(file_path: str) -> pd.DataFrame:
    """Ingests legacy CSV transaction logs and normalizes column headers."""
    df = pd.read_csv(file_path)
    df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')
    return df

def query_transaction_db(db_path: str, query: str) -> pd.DataFrame:
    """Executes SQL queries via DuckDB for rapid ledger analytics."""
    conn = duckdb.connect(db_path)
    result = conn.execute(query).df()
    conn.close()
    return result
