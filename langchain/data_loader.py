"""
data_loader.py
--------------
Loads all CSV files once at startup.
Every node imports from here so pandas DataFrames are never recreated mid-run.
"""

import pandas as pd
pd = pd
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

def _load(filename: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        return pd.read_csv(path)
    # Return empty DataFrame with expected shape if file missing (safe fallback)
    print(f"⚠️  Warning: {filename} not found at {path}. Using empty DataFrame.")
    return pd.DataFrame()

customers_df        = _load("customers.csv")
email_otp_df        = _load("email_otp.csv")
sms_otp_df          = _load("sms_otp.csv")
site_issues_df      = _load("site_issues.csv")
sites_df            = _load("sites.csv")
weekly_metrics_df   = _load("weekly_metrics.csv")
tickets_df          = _load("service_tickets.csv")
agent_avail_df      = _load("agent_availability.csv")
proposals_df        = _load("proposals.csv")
proposal_tmpl_df    = _load("proposal_template.csv")
crm_df              = _load("crm_opportunities.csv")
prospects_df        = _load("prospects.csv")
component_df        = _load("component_info.csv")


def get_next_ticket_id() -> str:
    """Generate a unique ticket ID as MAX(ticket_id)+1."""
    if tickets_df.empty or "ticket_id" not in tickets_df.columns:
        return "TKT-1001"
    max_id = tickets_df["ticket_id"].max()
    try:
        return f"TKT-{int(max_id) + 1}"
    except Exception:
        return f"TKT-1001"


def is_service_agent_online() -> bool:
    """Return True if at least one Service agent is currently online."""
    if agent_avail_df.empty:
        return False
    online = agent_avail_df[
        (agent_avail_df["department"].str.lower() == "service") &
        (agent_avail_df["is_online"] == True)
    ]
    return not online.empty


def is_sales_agent_online() -> bool:
    """Return True if at least one Sales / Inside-Sales agent is currently online."""
    if agent_avail_df.empty:
        return False
    online = agent_avail_df[
        (agent_avail_df["department"].str.lower().isin(["sales", "inside sales"])) &
        (agent_avail_df["is_online"] == True)
    ]
    return not online.empty
