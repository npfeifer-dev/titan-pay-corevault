# Titan Pay: CoreVault Enterprise Risk Engine & Reconciliation Dashboard

## Executive Summary
Following the strategic acquisition of a regional payment processing entity, Titan Pay faced a critical operational challenge: integrating fragmented, legacy accounting systems into a unified risk framework. The acquired firm relied heavily on manual, Excel-driven reconciliations, creating severe reporting lags, regulatory compliance risks, and unmonitored concentration exposure across corporate counterparties.

**CoreVault** was developed as an automated data pipeline and risk engine to solve this post-merger bottleneck. The platform ingests disparate transactional ledgers, standardizes GAAP financial metrics, and provides real-time risk visibility for Titan Pay’s Americas division credit committee.

## Core Problem & Business Impact
* **Legacy System Fragmentation:** Incompatible data structures between Titan Pay’s modern cloud infrastructure and the acquired entity's legacy ledgers.
* **Audit & Compliance Risk:** Manual reconciliation processes hindered compliance with regulatory guidelines and delayed daily reporting cycles.
* **Credit & Concentration Exposure:** Lack of centralized oversight for merchant concentration risk, counterparty evaluation, and payout anomalies.

## Architectural Solution
The engine acts as a centralized middleware layer that automates the end-to-end data lifecycle:

1. **Automated Data Ingestion & Harmonization:** Ingests raw transactional logs from legacy CSV exports alongside modern API feeds, standardizing schema architectures.
2. **Financial Logic Engine (GAAP Alignment):** Normalizes financial metrics across systems to accurately assess counterparty credit risk and daily merchant settlements.
3. **Anomaly & Revenue Leakage Detection:** Automatically flags transactional discrepancies, unusual refund volume spikes, and margin compression in real time.
4. **Audit-Ready Analytics Layer:** Generates clean, structured datasets optimized for business intelligence (BI) dashboards and executive reporting.

## Tech Stack
* **Language & Querying:** Python, SQL (DuckDB)
* **Data Manipulation:** Pandas, NumPy
* **Financial Calculations:** Custom modular Python scripts (`src/calculations.py`)
* **Environment:** Jupyter Notebooks, Visual Studio Code

## Project Structure
```text
├── data/
│   ├── raw/                   # Anonymized legacy ledgers & sample transaction logs
│   └── processed/             # Cleaned, standardized DataFrames ready for analysis
├── notebooks/
│   ├── 01_etl_and_cleaning.ipynb    # Data harmonization & legacy ledger integration
│   └── 02_risk_model_and_sql.ipynb  # Core risk logic, GAAP metrics, & SQL analytics
├── src/
│   ├── __init__.py
│   ├── data_loader.py         # Automated ingestion pipelines
│   └── calculations.py        # Financial metrics & anomaly flagging functions
├── .gitignore                 # Excludes cache, virtual environments, raw credentials
├── README.md                  # Project documentation
└── requirements.txt           # Python package dependencies

## Setup & Execution

### Prerequisites
* Python 3.9 or higher installed

### Installation & Setup

1. **Clone the Repository:**
'''
git clone https://github.com/npfeifer-dev/titan-pay-corevault.git
cd titan-pay-corevault
'''
2. **Set up a Virtual Environment:**
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
Install Dependencies:

3.**Install Dependencies:**
pip install -r requirements.txt

4. **Run the Notebooks:**
Launch Jupyter Notebook or VS Code to run notebooks/01_etl_and_cleaning.ipynb and execute the pipeline step-by-step.
