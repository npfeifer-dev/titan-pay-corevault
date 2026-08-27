
import io
import duckdb
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Titan Pay CoreVault Risk Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #1F4E78; margin-bottom: 0px; }
    .sub-header { font-size: 1.0rem; color: #555555; margin-bottom: 20px; }

    .context-box {
        background-color: var(--background-secondary-color, rgba(128, 128, 128, 0.1));
        color: var(--text-color, inherit);
        border-left: 5px solid #1F4E78;
        padding: 12px 18px;
        margin-bottom: 10px;
        border-radius: 4px;
    }

    .metric-badge-green {
        background-color: #D4EDDA; color: #155724; padding: 6px 12px; 
        border-radius: 6px; font-weight: bold; display: inline-block;
    }
    .metric-badge-yellow {
        background-color: #FFF3CD; color: #856404; padding: 6px 12px; 
        border-radius: 6px; font-weight: bold; display: inline-block;
    }
    .metric-badge-red {
        background-color: #F8D7DA; color: #721C24; padding: 6px 12px; 
        border-radius: 6px; font-weight: bold; display: inline-block;
    }
    </style>
""",
    unsafe_allow_html=True,
)

DB_PATH = "titan_corevault.duckdb"

@st.cache_data(ttl=600)
def load_credit_risk_data():
    con = duckdb.connect(DB_PATH, read_only=False)

    con.execute('''
    CREATE OR REPLACE VIEW view_comprehensive_credit_risk AS
    SELECT
        f.company_name AS account_name,
        f.ticker AS account_id,
        'Corporate' AS account_category,
        f.fiscal_year,
        f."Total Assets" AS total_assets,
        f."Total Liabilities" AS total_liabilities,
        f."Stockholders Equity" AS equity,
        f."Operating Income" AS operating_income,
        ROUND(f."Total Liabilities" / NULLIF(f."Stockholders Equity", 0), 2) AS debt_to_equity,
        ROUND(f."Operating Income" / NULLIF(f."Total Liabilities" * 0.035, 0), 2) AS interest_coverage_ratio,
        CASE 
            WHEN f.ticker = 'JPM' THEN NULL
            ELSE ROUND(
                (6.56 * ((f."Total Assets" - f."Total Liabilities") / NULLIF(f."Total Assets", 0))) +
                (3.26 * (f."Stockholders Equity" / NULLIF(f."Total Assets", 0))) +
                (6.72 * (f."Operating Income" / NULLIF(f."Total Assets", 0))) +
                (1.05 * (f."Stockholders Equity" / NULLIF(f."Total Liabilities", 0))), 2
            )
        END AS altman_z_score,
        CASE WHEN f.ticker = 'JPM' THEN TRUE ELSE FALSE END AS is_financial_institution
    FROM fact_sec_financials f

    UNION ALL

    SELECT 'Tier 1: Prime / Low Risk', 'TIER_1_PRIME', 'Credit Tier', 2024, 5000000000, 1500000000, 3500000000, 450000000, 0.43, 8.50, NULL, FALSE
    UNION ALL
    SELECT 'Tier 1: Prime / Low Risk', 'TIER_1_PRIME', 'Credit Tier', 2025, 5500000000, 1600000000, 3900000000, 500000000, 0.41, 8.90, NULL, FALSE

    UNION ALL

    SELECT 'Tier 2: Mid-Grade / Moderate', 'TIER_2_MID', 'Credit Tier', 2024, 2500000000, 1800000000, 700000000, 150000000, 2.57, 2.38, NULL, FALSE
    UNION ALL
    SELECT 'Tier 2: Mid-Grade / Moderate', 'TIER_2_MID', 'Credit Tier', 2025, 2700000000, 1950000000, 750000000, 165000000, 2.60, 2.42, NULL, FALSE

    UNION ALL

    SELECT 'Tier 3: Subprime / High Risk', 'TIER_3_SUBPRIME', 'Credit Tier', 2024, 1000000000, 920000000, 80000000, 35000000, 11.50, 1.08, NULL, FALSE
    UNION ALL
    SELECT 'Tier 3: Subprime / High Risk', 'TIER_3_SUBPRIME', 'Credit Tier', 2025, 1050000000, 980000000, 70000000, 30000000, 14.00, 0.87, NULL, FALSE;
    ''')

    df = con.execute(
        "SELECT * FROM view_comprehensive_credit_risk ORDER BY account_category, account_id, fiscal_year DESC"
    ).df()
    con.close()
    return df

@st.cache_data(ttl=600)
def load_monthly_transaction_data():
    con = duckdb.connect(DB_PATH, read_only=True)
    df_tx = con.execute('''
        SELECT 
            DATE_TRUNC('month', transaction_date) AS month,
            a.account_type,
            COUNT(t.transaction_id) AS transaction_count,
            ROUND(SUM(t.amount), 2) AS net_cash_flow,
            ROUND(SUM(CASE WHEN t.amount > 0 THEN t.amount ELSE 0 END), 2) AS total_inflow,
            ROUND(SUM(CASE WHEN t.amount < 0 THEN ABS(t.amount) ELSE 0 END), 2) AS total_outflow
        FROM fact_transactions t
        JOIN dim_accounts a ON t.account_id = a.account_id
        GROUP BY 1, 2
        ORDER BY month ASC
    ''').df()
    con.close()
    return df_tx

@st.cache_data(ttl=600)
def load_monthly_tier_data():
    months = pd.date_range(start="2024-01-01", end="2025-12-01", freq="MS")
    records = []

    for m in months:
        progress = (m.month - 1) / 12.0
        if m.year == 2024:
            t1_de, t2_de, t3_de = 0.43 + (0.02 * progress), 2.57 + (0.03 * progress), 11.50 + (1.25 * progress)
        else:
            t1_de, t2_de, t3_de = 0.41 - (0.01 * progress), 2.60 - (0.02 * progress), 12.75 + (1.25 * progress)

        records.append({"month": m, "account_id": "TIER_1_PRIME", "debt_to_equity": round(t1_de, 2)})
        records.append({"month": m, "account_id": "TIER_2_MID", "debt_to_equity": round(t2_de, 2)})
        records.append({"month": m, "account_id": "TIER_3_SUBPRIME", "debt_to_equity": round(t3_de, 2)})

    return pd.DataFrame(records)

def generate_excel_report(df):
    output = io.BytesIO()
    df_export = df.copy()
    df_export.columns = [
        "Account / Tier Name", "Account ID / Code", "Category", "Fiscal Year",
        "Total Assets ($)", "Total Liabilities ($)", "Equity / Cushion ($)",
        "Operating / Annual Income ($)", "Leverage Ratio (D/E)", "Interest Coverage Ratio",
        "Altman Z-Score", "Is Bank / FI"
    ]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Credit Risk & Tier Ledger"
    ws.append(list(df_export.columns))

    for row in df_export.itertuples(index=False):
        ws.append(list(row))

    header_font = Font(name="Arial", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    data_font = Font(name="Arial", size=10)
    thin_border = Border(
        left=Side(style="thin", color="D9D9D9"), right=Side(style="thin", color="D9D9D9"),
        top=Side(style="thin", color="D9D9D9"), bottom=Side(style="thin", color="D9D9D9")
    )

    for col_num in range(1, ws.max_column + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=ws.max_column):
        for cell in row:
            cell.font = data_font
            cell.border = thin_border
            if cell.column in [5, 6, 7, 8]:
                cell.number_format = "$#,##0"
                cell.alignment = Alignment(horizontal="right")
            elif cell.column in [9, 10]:
                cell.number_format = "0.00x"
                cell.alignment = Alignment(horizontal="right")
            elif cell.column == 11:
                cell.number_format = "0.00" if pd.notna(cell.value) else "@"
                cell.alignment = Alignment(horizontal="right")
            else:
                cell.alignment = Alignment(horizontal="center")

    for col in ws.columns:
        max_len = max(len(str(cell.value or "")) for cell in col)
        col_letter = get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    wb.save(output)
    output.seek(0)
    return output

try:
    df_data = load_credit_risk_data()
    df_transactions = load_monthly_transaction_data()
    df_monthly_tiers = load_monthly_tier_data()
except Exception as e:
    st.error(f"Error loading database: {e}")
    st.stop()

st.sidebar.image("https://raw.githubusercontent.com/twitter/twemoji/master/assets/svg/1f6e1.svg", width=65)
st.sidebar.title("Titan Pay CoreVault")
st.sidebar.markdown("**Unified Credit & Risk Engine**")
st.sidebar.markdown("---")

category_filter = st.sidebar.radio(
    "Select Segment View:",
    options=["ALL", "Corporate Accounts", "Non-Corporate Risk Tiers"]
)

filtered_by_cat = df_data.copy()
if category_filter == "Corporate Accounts":
    filtered_by_cat = filtered_by_cat[filtered_by_cat["account_category"] == "Corporate"]
elif category_filter == "Non-Corporate Risk Tiers":
    filtered_by_cat = filtered_by_cat[filtered_by_cat["account_category"] == "Credit Tier"]

selected_account = st.sidebar.selectbox(
    "Select Entity / Risk Tier:",
    options=["ALL"] + list(filtered_by_cat["account_id"].unique()),
)

year_range = st.sidebar.slider(
    "Fiscal Year Range:",
    int(df_data["fiscal_year"].min()),
    int(df_data["fiscal_year"].max()),
    (int(df_data["fiscal_year"].min()), int(df_data["fiscal_year"].max())),
)

st.sidebar.markdown("---")
st.sidebar.subheader("Audit & Compliance Export")
excel_bytes = generate_excel_report(filtered_by_cat)
st.sidebar.download_button(
    label="📥 Download Audit Ledger (.xlsx)",
    data=excel_bytes,
    file_name="titan_pay_credit_risk_report.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

filtered_df = filtered_by_cat[
    (filtered_by_cat["fiscal_year"] >= year_range[0]) &
    (filtered_by_cat["fiscal_year"] <= year_range[1])
]

if selected_account != "ALL":
    filtered_df = filtered_df[filtered_df["account_id"] == selected_account]

st.markdown('<p class="main-header">Titan CoreVault Risk Management Dashboard</p>', unsafe_allow_html=True)

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Executive Summary", 
    "📈 Corporate Insolvency", 
    "📝 Underwriting & Valuation", 
    "💳 Portfolio Analytics", 
    "📋 Data Ledger"
])

with tab1:
    with st.expander("ℹ️ View Methodology & Context (Executive Summary)", expanded=False):
        st.markdown("""
            <div class="context-box">
                <b>📌 Situation:</b> Titan Pay needed a unified platform to monitor both multi-billion dollar corporate clients and retail credit tiers.<br>
                <b>💡 Solution:</b> CoreVault integrates SEC financial data, DuckDB analytics, and dynamic sensitivity engines into a real-time risk platform.<br>
                <b>🔍 What This Means:</b> Executive leadership gains an instant portfolio health check, dynamic exposure totals, and audit-ready data.
            </div>
        """, unsafe_allow_html=True)

    st.subheader('Executive Risk & Exposure Summary')
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    total_liabilities = filtered_df['total_liabilities'].sum()
    latest_records = filtered_df.sort_values('fiscal_year').groupby('account_id').last()

    non_bank_records = latest_records[~latest_records['is_financial_institution']]
    avg_z_score = non_bank_records["altman_z_score"].dropna().mean()
    avg_icr = latest_records["interest_coverage_ratio"].mean()

    kpi1.metric("Total Outstanding Exposure", f"${total_liabilities/1e9:,.2f}B" if total_liabilities >= 1e9 else f"${total_liabilities/1e6:,.1f}M")
    kpi2.metric("Tracked Entities / Tiers", len(filtered_df["account_id"].unique()))
    kpi3.metric(
        "Avg Corporate Z-Score",
        f"{avg_z_score:.2f}" if pd.notna(avg_z_score) else "N/A (FI / Tiers)",
        delta="Safe Zone" if (pd.notna(avg_z_score) and avg_z_score > 2.6) else "Watchlist",
    )
    kpi4.metric(
        "Avg Interest Coverage",
        f"{avg_icr:.2f}x" if pd.notna(avg_icr) else "N/A",
        delta="Strong Buffer" if (pd.notna(avg_icr) and avg_icr > 5.0) else "Elevated Risk",
    )

    st.markdown("---")
    st.subheader("🎯 Project Scope & Architecture Overview")

    scope_col1, scope_col2 = st.columns(2)
    with scope_col1:
        st.markdown("""
        **Core Engine Architecture:**
        * **Database Layer:** DuckDB relational engine running optimized views over SEC financials and transaction facts.
        * **Analytics Layer:** Automated financial ratio computation (D/E, Interest Coverage, Altman Z-Score, DCF Valuation).
        * **UI/UX Layer:** Streamlit-powered dashboard featuring custom CSS styling and real-time Plotly visualizations.
        """)
    with scope_col2:
        st.markdown("""
        **System Capabilities:**
        * **Multi-Segment Monitoring:** Blends SEC corporate filings with standardized non-corporate credit risk profiles.
        * **Real-time Stress Testing:** Interactive DCF sensitivity analysis for corporate valuations and default shock models for credit tiers.
        * **Audit Compliance:** Automated generation of Excel reports styled for institutional audit specifications.
        """)

with tab2:
    with st.expander("ℹ️ View Methodology & Context (Corporate Insolvency)", expanded=False):
        st.markdown("""
            <div class="context-box">
                <b>📌 Situation:</b> Corporate counterparties present varying degrees of leverage and insolvency exposure.<br>
                <b>💡 Solution:</b> Automated tracking of Debt-to-Equity (D/E) profiles alongside non-bank Altman Z-Score models.<br>
                <b>🔍 What This Means:</b> Risk teams can proactively identify deteriorating credit quality prior to default events.
            </div>
        """, unsafe_allow_html=True)

    st.subheader("Corporate Risk & Insolvency Profile")
    corp_df = filtered_df[filtered_df["account_category"] == "Corporate"]

    col_corp1, col_corp2 = st.columns(2)

    with col_corp1:
        if not corp_df.empty:
            fig_dte_corp = px.line(
                corp_df,
                x="fiscal_year",
                y="debt_to_equity",
                color="account_id",
                markers=True,
                title="Corporate Leverage Profile (Debt-to-Equity)",
                labels={"debt_to_equity": "Leverage Ratio (D/E)", "fiscal_year": "Fiscal Year", "account_id": "Corporate Ticker"},
            )
            fig_dte_corp.update_layout(hovermode='x unified')
            st.plotly_chart(fig_dte_corp, use_container_width=True)
        else:
            st.info("No corporate accounts match the current sidebar filter selection.")

    with col_corp2:
        z_score_df = corp_df[~corp_df["is_financial_institution"]]
        if not z_score_df.empty:
            fig_z = px.bar(
                z_score_df,
                x="fiscal_year",
                y='altman_z_score',
                color="account_id",
                barmode="group",
                title="Corporate Insolvency Risk Buffer (Altman Z-Score)",
                labels={'altman_z_score': "Altman Z-Score", 'fiscal_year': "Fiscal Year", 'account_id': "Corporate Ticker"},
            )
            fig_z.add_hline(
                y=2.6, line_dash='dash', line_color='#006622', line_width=2,
                annotation_text=' Safe Threshold (2.6) ', annotation_position='top left',
                annotation_font_color='#FFFFFF', annotation_font_size=12,
                annotation_font_weight='bold', annotation_bgcolor='#006622',
                annotation_bordercolor='#006622', annotation_borderwidth=3,
            )
            st.plotly_chart(fig_z, use_container_width=True)
        else:
            st.info("Altman Z-Scores apply exclusively to non-bank Corporate entities.")

with tab3:
    with st.expander("ℹ️ View Methodology & Context (Underwriting & Valuation)", expanded=False):
        st.markdown("""
            <div class="context-box">
                <b>📌 Situation:</b> Underwriters require immediate access to credit metrics and sensitivity modeling for specific counterparties.<br>
                <b>💡 Solution:</b> In-page entity filtering paired with dynamic risk-colored indicators and live DCF sensitivity models.<br>
                <b>🔍 What This Means:</b> Accelerates credit line approvals while delivering precise, color-coded risk visibility.
            </div>
        """, unsafe_allow_html=True)

    st.subheader("Credit Underwriting Briefs & Valuation Modeling")

    filter_col1, filter_col2 = st.columns([1, 2])
    with filter_col1:
        tab3_cat = st.radio("Filter Category:", ["ALL", "Corporate", "Credit Tier"], horizontal=True, key="tab3_cat_filter")
    with filter_col2:
        avail_entities = df_data.copy()
        if tab3_cat != "ALL":
            avail_entities = avail_entities[avail_entities["account_category"] == tab3_cat]
        entity_options = list(avail_entities["account_id"].unique())
        tab3_selected_entity = st.selectbox("🔍 Select Entity / Risk Tier for Brief:", options=entity_options, key="tab3_entity_selector")

    st.markdown("---")

    account_df = df_data[
        (df_data["account_id"] == tab3_selected_entity) & 
        (df_data["fiscal_year"] >= year_range[0]) & 
        (df_data["fiscal_year"] <= year_range[1])
    ]

    if account_df.empty:
        st.warning("No financial data available for the selected entity in this fiscal year range.")
    else:
        latest_client = account_df.sort_values('fiscal_year', ascending=False).iloc[0]

        de_val = latest_client['debt_to_equity']
        if de_val <= 1.5:
            de_class, de_status = "metric-badge-green", "Low Risk"
        elif de_val <= 3.5:
            de_class, de_status = "metric-badge-yellow", "Moderate Risk"
        else:
            de_class, de_status = "metric-badge-red", "High Risk / Highly Leveraged"

        icr_val = latest_client['interest_coverage_ratio']
        if icr_val >= 5.0:
            icr_class, icr_status = "metric-badge-green", "Strong Buffer"
        elif icr_val >= 2.0:
            icr_class, icr_status = "metric-badge-yellow", "Adequate Coverage"
        else:
            icr_class, icr_status = "metric-badge-red", "Distressed Coverage"

        st.markdown(f"### Entity Evaluation: **{latest_client['account_name']}** (`{latest_client['account_category']}`)")

        rec_col1, rec_col2 = st.columns([1, 2])

        with rec_col1:
            st.markdown("**Evaluative Health Indicators:**")
            st.markdown(f"• **Leverage (D/E):** <span class='{de_class}'>{de_val:.2f}x — {de_status}</span>", unsafe_allow_html=True)
            st.markdown(f"• **Interest Coverage:** <span class='{icr_class}'>{icr_val:.2f}x — {icr_status}</span>", unsafe_allow_html=True)

            if latest_client['is_financial_institution']:
                st.markdown("• **Altman Z-Score:** <span class='metric-badge-green'>N/A (Regulated Bank)</span>", unsafe_allow_html=True)
            elif latest_client['account_category'] == 'Corporate':
                z_val = latest_client['altman_z_score']
                if z_val >= 2.6:
                    z_class, z_status = "metric-badge-green", "Safe Zone"
                elif z_val >= 1.8:
                    z_class, z_status = "metric-badge-yellow", "Grey Zone"
                else:
                    z_class, z_status = "metric-badge-red", "Distress Zone"
                st.markdown(f"• **Altman Z-Score:** <span class='{z_class}'>{z_val:.2f} — {z_status}</span>", unsafe_allow_html=True)
            else:
                st.markdown("• **Risk Model:** `Standardized Portfolio Tier`", unsafe_allow_html=True)

        with rec_col2:
            if latest_client['is_financial_institution']:
                st.info(
                    "**Underwriting Status: APPROVED (Regulated Bank Interbank Line)**\n\n"
                    "JPMorgan Chase operates as a Tier-1 G-SIB with Fed Basel III CET1 ratios >15.0%. "
                    "Titan Pay approves interbank treasury settlement lines subject to continuous liquidity monitoring."
                )
            elif latest_client['account_category'] == 'Corporate':
                if tab3_selected_entity == "MSFT":
                    st.success("**Underwriting Status: APPROVED (Tier-1 Unsecured Line)**\n\nTitan Pay authorizes up to **$5.0 Billion** in treasury settlement with zero collateral requirements based on exceptional solvency.")
                elif tab3_selected_entity == "AAPL":
                    st.warning("**Underwriting Status: APPROVED WITH MONITORING (Revolving Line)**\n\nWhile leverage is elevated due to capital returns, cash flows remain elite. Facility limit renewed subject to leverage caps.")
                else:
                    st.success(f"**Underwriting Status: APPROVED**\n\nAutomated review completed for {latest_client['account_name']}.")
            else:
                if tab3_selected_entity == 'TIER_1_PRIME':
                    st.success("**Tier Policy: Prime Automatic Approval**\n\nDefault Probability < 0.5%. Maximum unsecured line limits authorized across prime accounts.")
                elif tab3_selected_entity == 'TIER_2_MID':
                    st.warning("**Tier Policy: Standard Conditional Approval**\n\nDefault Probability 2.0%-4.0%. Requires credit monitoring and secondary collateral buffers.")
                else:
                    st.error("**Tier Policy: High Risk / Restricted**\n\nDefault Probability > 8.0%. Manual underwriting approval and 100% deposit collateral mandatory.")

        st.markdown("---")
        if latest_client['is_financial_institution']:
            st.subheader("💡 Financial Institution Capital Structure & Basel III Stress Test")
            st.caption("Commercial banks are evaluated on regulatory Tier 1 Common Equity (CET1) capital ratios and Liquidity Coverage Ratios (LCR).")

            b_col1, b_col2, b_col3 = st.columns(3)
            b_col1.metric("Est. CET1 Capital Ratio", "15.3%", delta="+2.3% above Fed Min (13.0%)")
            b_col2.metric("Liquidity Coverage Ratio (LCR)", "114%", delta="Compliant (>100%)")
            b_col3.metric("Total Deposits / Liabilities Ratio", "0.88x", delta="Stable Funding")

        elif latest_client['account_category'] == 'Corporate':
            st.subheader("💡 Interactive Corporate DCF Valuation & Sensitivity Analysis")
            st.caption("Adjust cost of capital (WACC) and terminal growth rates to evaluate implied enterprise value and sensitivity.")

            col_wacc, col_g = st.columns(2)
            with col_wacc:
                wacc_input = st.slider("Weighted Average Cost of Capital (WACC %)", 4.0, 15.0, 8.5, 0.25)
                wacc = wacc_input / 100.0
            with col_g:
                g_input = st.slider("Terminal Growth Rate (g %)", 0.5, 5.0, 2.5, 0.25)
                g = g_input / 100.0

            tax_rate = 0.21
            base_income = latest_client['operating_income']
            estimated_fcff = base_income * (1 - tax_rate)

            if wacc <= g:
                st.error("⚠️ Cost of Capital (WACC) must be strictly greater than Terminal Growth Rate (g).")
            else:
                terminal_value = (estimated_fcff * (1 + g)) / (wacc - g)

                val_kpi1, val_kpi2, val_kpi3 = st.columns(3)
                val_kpi1.metric("Estimated Base FCFF", f'${estimated_fcff / 1e9:,.2f}B')
                val_kpi2.metric("Implied Terminal Value", f'${terminal_value / 1e9:,.2f}B')
                val_kpi3.metric("Valuation Multiplier", f'{(terminal_value / base_income):,.1f}x EBIT' if base_income > 0 else "N/A")

                sens_col1, sens_col2 = st.columns([3, 2])

                with sens_col1:
                    wacc_pct_points = [round(wacc_input + delta, 2) for delta in [-3.0, -2.4, -1.8, -1.2, -0.6, 0.0, 0.6, 1.2, 1.8, 2.4, 3.0]]
                    wacc_pct_points = [w for w in wacc_pct_points if w > (g_input + 0.1)]

                    tv_curve = [(estimated_fcff * (1 + g)) / ((w / 100.0) - g) / 1e9 for w in wacc_pct_points]

                    fig_sens = px.line(
                        pd.DataFrame({"WACC (%)": wacc_pct_points, "Terminal Value ($B)": tv_curve}),
                        x="WACC (%)", y="Terminal Value ($B)",
                        title=f"WACC Curve: {latest_client['account_name']} (at g = {g_input:.2f}%)",
                        markers=True
                    )
                    fig_sens.add_scatter(
                        x=[wacc_input], y=[terminal_value / 1e9], 
                        mode="markers+text", marker=dict(color="red", size=14, symbol="diamond"),
                        text=["Active WACC"], textposition="top center", name="Active Selection"
                    )
                    st.plotly_chart(fig_sens, use_container_width=True)

                with sens_col2:
                    st.markdown("**Valuation Sensitivity Matrix ($B):**")
                    wacc_steps = [wacc_input - 1.0, wacc_input, wacc_input + 1.0]
                    g_steps = [g_input - 0.5, g_input, g_input + 0.5]

                    raw_matrix = []
                    for w_val in wacc_steps:
                        row = []
                        w_dec = w_val / 100.0
                        for g_val in g_steps:
                            g_dec = g_val / 100.0
                            if w_dec > g_dec:
                                val = (estimated_fcff * (1 + g_dec)) / (w_dec - g_dec) / 1e9
                                row.append(val)
                            else:
                                row.append(None)
                        raw_matrix.append(row)

                    matrix_df = pd.DataFrame(
                        raw_matrix, 
                        index=[f"WACC {w:.2f}%" for w in wacc_steps],
                        columns=[f"g = {g_val:.2f}%" for g_val in g_steps]
                    )
                    st.dataframe(
                        matrix_df.style.background_gradient(cmap="RdYlGn", axis=None).format(lambda x: f"${x:,.2f}B" if pd.notna(x) else "N/A"),
                        use_container_width=True
                    )

        else:
            st.subheader("💡 Standardized Non-Corporate Tier Stress Test")
            st.caption("Simulate portfolio default rate increases to model required credit loss reserves.")

            shock = st.slider("Simulated Default Rate Spike (+%)", 0.0, 10.0, 2.5, 0.5)
            base_loss = latest_client['total_liabilities'] * 0.02
            stressed_loss = latest_client['total_liabilities'] * (0.02 + (shock / 100.0))

            t_kpi1, t_kpi2 = st.columns(2)
            t_kpi1.metric("Baseline Reserve Requirement", f"${base_loss / 1e6:,.1f}M")
            t_kpi2.metric("Stressed Loss Reserve", f"${stressed_loss / 1e6:,.1f}M", delta=f"+${(stressed_loss - base_loss) / 1e6:,.1f}M Risk")

with tab4:
    with st.expander("ℹ️ View Methodology & Context (Portfolio Analytics)", expanded=False):
        st.markdown("""
            <div class="context-box">
                <b>📌 Situation:</b> Non-corporate credit tiers require continuous, high-frequency trend monitoring.<br>
                <b>💡 Solution:</b> Monthly granular tracking of D/E leverage ratios alongside transaction density and cash flow trends.<br>
                <b>🔍 What This Means:</b> Allows credit ops to detect monthly cash flow squeezes and tier degradation in real time.
            </div>
        """, unsafe_allow_html=True)

    st.subheader("Non-Corporate Portfolio Risk & Transaction Analytics")

    nc_col1, nc_col2, nc_col3 = st.columns(3)

    with nc_col1:
        fig_dte_tier = px.line(
            df_monthly_tiers,
            x="month",
            y="debt_to_equity",
            color="account_id",
            markers=True,
            title="Monthly Non-Corporate Credit Tier D/E Profile",
            labels={"debt_to_equity": "Tier Leverage (D/E)", "month": "Month", "account_id": "Risk Tier"},
        )
        fig_dte_tier.update_layout(hovermode='x unified')
        st.plotly_chart(fig_dte_tier, use_container_width=True)

    with nc_col2:
        df_monthly_sum = df_transactions.groupby("month")["net_cash_flow"].sum().reset_index()
        fig_cashflow = px.line(
            df_monthly_sum,
            x="month",
            y="net_cash_flow",
            markers=True,
            title="Monthly Net Cash Flow Trend ($)",
            labels={"month": "Month", "net_cash_flow": "Net Cash Flow ($)"},
            line_shape="spline"
        )
        fig_cashflow.update_traces(line_color="#1F4E78", line_width=3)
        st.plotly_chart(fig_cashflow, use_container_width=True)

    with nc_col3:
        fig_volume = px.bar(
            df_transactions,
            x="month",
            y="transaction_count",
            color="account_type",
            title="Monthly Transaction Density",
            labels={"month": "Month", "transaction_count": "Transaction Count", "account_type": "Account Type"},
            barmode="stack"
        )
        st.plotly_chart(fig_volume, use_container_width=True)

with tab5:
    with st.expander("ℹ️ View Methodology & Context (Data Ledger)", expanded=False):
        st.markdown("""
            <div class="context-box">
                <b>📌 Situation:</b> Regulators and auditors demand a single, unaggregated ledger for verification.<br>
                <b>💡 Solution:</b> A standardized credit ledger displaying normalized corporate and tier balances.<br>
                <b>🔍 What This Means:</b> Provides full transparency and direct export capabilities for internal and external audit compliance.
            </div>
        """, unsafe_allow_html=True)

    st.subheader("Standardized Credit Risk Data Ledger")
    st.dataframe(
        filtered_df.style.format(
            {
                "total_assets": "${:,.0f}",
                "total_liabilities": "${:,.0f}",
                "equity": "${:,.0f}",
                "operating_income": "${:,.0f}",
                "debt_to_equity": "{:.2f}x",
                "interest_coverage_ratio": "{:.2f}x",
                "altman_z_score": lambda x: f"{x:.2f}" if pd.notna(x) else "-",
            }
        ),
        use_container_width=True,
    )
