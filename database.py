# database.py — CSV loading + all data helper functions
# Column reference (from actual CSVs):
#   customers.csv   : customer_id, name, email, phone, location, site_id, has_proposals
#   prospects.csv   : prospect_id, email, phone, proposal_ids
#   email_otp.csv   : email, otp, timestamp
#   sms_otp.csv     : phone, otp, timestamp
#   sites.csv       : site_id, customer_id, address, system_size_kw, inverter_brand,
#                     module_brand, installation_date, issue_flag, issue_text,
#                     recommended_action_text
#   site_issues.csv : site_id, issue_flag, issue_text, recommended_action_text
#   weekly_metrics.csv : metric_id, site_id, date, production_kwh,
#                        cloudiness_percentage, performance_score, weather_conditions
#   proposals.csv   : proposal_id, customer_id, proposal_name, approx_price,
#                     estimated_yearly_savings, date_created, status,
#                     system_size_kw, inverter_brand, module_brand
#   proposal_template: proposal_id, category, proposal_name, system_size_kw,
#                      inverter_brand, module_brand, approx_price, estimated_yearly_savings
#   service_tickets.csv : ticket_id, customer_id, site_id, issue_category,
#                         description, status, date_created
#   agent_availability.csv : agent_id, agent_name, department, is_online

import os
import math
import hashlib
import pandas as pd
from config import DATA_DIR, DEFAULT_OTP
from datetime import date


# ─────────────────────────────────────────────
# CSV LOADING
# ─────────────────────────────────────────────

def _load(filename):
    path = os.path.join(DATA_DIR, filename)
    try:
        return pd.read_csv(path)
    except Exception as e:
        print(f"[WARN] Could not load {filename}: {e}")
        return pd.DataFrame()


customers_df   = _load("customers.csv")
prospects_df   = _load("prospects.csv")
email_otp_df   = _load("email_otp.csv")
sms_otp_df     = _load("sms_otp.csv")
sites_df       = _load("sites.csv")
site_issues_df = _load("site_issues.csv")
weekly_df      = _load("weekly_metrics.csv")
proposals_df   = _load("proposals.csv")
tickets_df     = _load("service_tickets.csv")
agents_df      = _load("agent_availability.csv")


# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────

def lookup_user(id_type: str, contact: str):
    """
    Returns (customer_dict | None, prospect_dict | None).
    Checks customers.csv first (by email or phone), then prospects.csv.
    Prospect dict is normalised to look like a customer dict.
    """
    contact = contact.strip()

    # ── customers ─────────────────────────────
    cust = None
    if not customers_df.empty and id_type in customers_df.columns:
        match = customers_df[
            customers_df[id_type].astype(str).str.strip() == contact
        ]
        if not match.empty:
            cust = match.iloc[0].to_dict()

    # ── prospects ─────────────────────────────
    pros = None
    if not prospects_df.empty and id_type in prospects_df.columns:
        match = prospects_df[
            prospects_df[id_type].astype(str).str.strip() == contact
        ]
        if not match.empty:
            row = match.iloc[0].to_dict()
            # normalise to customer-like shape so the rest of the code is uniform
            pros = {
                "customer_id":   str(row.get("prospect_id", "PROSPECT")),
                "name":          row.get("name", "Valued Customer"),
                "email":         row.get("email", ""),
                "phone":         row.get("phone", ""),
                "location":      row.get("location", ""),
                "site_id":       None,
                "has_proposals": bool(row.get("proposal_ids", "")),
                "_proposal_ids": str(row.get("proposal_ids", "")),
                "_is_prospect":  True,
            }

    return cust, pros


def get_otp(id_type: str, contact: str) -> str:
    contact = contact.strip()
    if id_type == "email":
        df, col = email_otp_df, "email"
    else:
        df, col = sms_otp_df, "phone"

    if not df.empty and col in df.columns:
        match = df[df[col].astype(str).str.strip() == contact]
        if not match.empty:
            return str(match.iloc[0]["otp"]).strip()

    return DEFAULT_OTP


def _bool(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes")


# ─────────────────────────────────────────────
# SERVICE HELPERS
# ─────────────────────────────────────────────

def get_monitoring(site_id) -> dict:
    """
    Returns monitoring dict for a site.
    Prefers sites.csv issue_flag; falls back to weekly_metrics.
    """
    if not site_id:
        return _no_data_monitoring()

    try:
        site_id_int = int(float(str(site_id)))
    except (ValueError, TypeError):
        return _no_data_monitoring()

    # ── Check sites.csv ───────────────────────
    if not sites_df.empty:
        row_df = sites_df[sites_df["site_id"] == site_id_int]
        if not row_df.empty:
            row = row_df.iloc[0]
            issue_flag = _bool(row.get("issue_flag", False))
            issue_text = str(row.get("issue_text", "")).strip()
            action_text = str(row.get("recommended_action_text", "")).strip()

            avg_cloud  = _get_avg_cloudiness(site_id_int)
            avg_perf   = _get_avg_performance(site_id_int)
            total_prod = _get_total_production(site_id_int)

            if issue_flag and issue_text:
                explanation = f"{issue_text}"
                if action_text:
                    explanation += f" — Recommended action: {action_text}"
                return {
                    "issue_flag":        True,
                    "explanation":       explanation,
                    "avg_cloudiness":    avg_cloud,
                    "performance_score": avg_perf,
                    "total_production":  total_prod,
                }

            # No active issue — compute from metrics
            return _compute_explanation(avg_cloud, avg_perf, total_prod)

    # ── Fallback: weekly_metrics only ─────────
    avg_cloud  = _get_avg_cloudiness(site_id_int)
    avg_perf   = _get_avg_performance(site_id_int)
    total_prod = _get_total_production(site_id_int)
    return _compute_explanation(avg_cloud, avg_perf, total_prod)


def _no_data_monitoring() -> dict:
    return {
        "issue_flag":        False,
        "explanation":       "No monitoring data found for this site.",
        "avg_cloudiness":    0,
        "performance_score": 0,
        "total_production":  0.0,
    }


def _compute_explanation(avg_cloud, avg_perf, total_prod) -> dict:
    if avg_cloud > 60:
        explanation = (
            f"No active faults detected. However, the last week was unusually cloudy "
            f"({avg_cloud}% average) at your location, which likely reduced production. "
            f"It should recover as weather improves."
        )
    elif avg_perf >= 90:
        explanation = (
            f"Your system is performing normally. "
            f"Last week's total production: {total_prod} kWh."
        )
    else:
        explanation = (
            f"System is operating. Last week: {total_prod} kWh. "
            f"We notice a slight underperformance trend — nothing critical yet, we're monitoring it."
        )
    return {
        "issue_flag":        False,
        "explanation":       explanation,
        "avg_cloudiness":    avg_cloud,
        "performance_score": avg_perf,
        "total_production":  total_prod,
    }


def _get_avg_cloudiness(site_id: int) -> int:
    if weekly_df.empty:
        return 0
    rows = weekly_df[weekly_df["site_id"] == site_id]
    if rows.empty:
        return 0
    return int(rows["cloudiness_percentage"].mean())


def _get_avg_performance(site_id: int) -> int:
    if weekly_df.empty:
        return 0
    rows = weekly_df[weekly_df["site_id"] == site_id]
    if rows.empty:
        return 0
    return int(rows["performance_score"].mean())


def _get_total_production(site_id: int) -> float:
    if weekly_df.empty:
        return 0.0
    rows = weekly_df[weekly_df["site_id"] == site_id]
    if rows.empty:
        return 0.0
    return round(float(rows["production_kwh"].sum()), 1)


# ─────────────────────────────────────────────
# AGENT AVAILABILITY
# ─────────────────────────────────────────────

def get_online_agent(department: str):
    """Returns first available online agent name, or None."""
    if agents_df.empty:
        return None
    avail = agents_df[
        (agents_df["department"].astype(str).str.strip() == department) &
        (agents_df["is_online"].astype(str).str.strip().str.lower().isin(["true", "1"]))
    ]
    return str(avail.iloc[0]["agent_name"]) if not avail.empty else None


# ─────────────────────────────────────────────
# PROPOSALS HELPERS
# ─────────────────────────────────────────────

def is_has_proposals(val) -> bool:
    return _bool(val)


def get_past_proposals(customer_id) -> list:
    """Fetch proposals from proposals.csv for a given customer_id."""
    if proposals_df.empty:
        return []
    rows = proposals_df[
        proposals_df["customer_id"].astype(str) == str(customer_id)
    ]
    return [_normalize_proposal(r) for _, r in rows.iterrows()]


def get_proposal_by_id(proposal_id) -> dict | None:
    """Look up a single proposal by proposal_id (int or str)."""
    if proposals_df.empty:
        return None
    try:
        pid = int(proposal_id)
    except (ValueError, TypeError):
        return None
    match = proposals_df[proposals_df["proposal_id"] == pid]
    if match.empty:
        return None
    return _normalize_proposal(match.iloc[0])


def _normalize_proposal(row) -> dict:
    """Standardise and clean a proposal row from any CSV."""
    d = row.to_dict() if hasattr(row, "to_dict") else dict(row)

    # Clean NaN / nan strings
    for k, v in d.items():
        if isinstance(v, float) and math.isnan(v):
            d[k] = None
        elif str(v).strip().lower() in ("nan", "none", ""):
            d[k] = None

    # Unify column naming
    if not d.get("system_size_kw"):
        d["system_size_kw"] = d.get("size_kw", 0)
    if not d.get("estimated_yearly_savings"):
        d["estimated_yearly_savings"] = d.get("yearly_savings", d.get("est_yearly_savings", 0))
    if not d.get("date_created"):
        d["date_created"] = d.get("created_at", "—")
    if not d.get("proposal_name"):
        d["proposal_name"] = d.get("name", f"Proposal #{d.get('proposal_id','')}")

    # Always compute monthly_savings from yearly if missing
    yearly = d.get("estimated_yearly_savings") or 0
    try:
        d["monthly_savings"] = round(float(yearly) / 12, 2)
    except (ValueError, TypeError):
        d["monthly_savings"] = 0

    # Ensure approx_price is always a display string
    if not d.get("approx_price"):
        size = float(d.get("system_size_kw") or 0)
        d["approx_price"] = f"${int(size * 1200):,} – ${int(size * 1500):,}"

    # Convert approx_price if it's a plain number
    try:
        price_num = float(str(d["approx_price"]).replace(",", ""))
        d["approx_price"] = f"${int(price_num):,}"
    except (ValueError, TypeError):
        pass  # Already a formatted string

    return d


def generate_proposals(city: str, segment: str, bill: float,
                        increase: float, num: int,
                        brand_pref: str, tier_pref: str) -> list:
    """
    Fully deterministic — same inputs always produce identical outputs.
    Uses md5 hash of inputs as seed so proposal IDs are stable.
    """
    seed_str  = f"{city}|{segment}|{bill}|{increase}|{brand_pref}|{tier_pref}"
    seed_hash = int(hashlib.md5(seed_str.encode()).hexdigest(), 16) % 8000

    tier_multipliers = {"Premium": 1.35, "Standard": 1.0, "Budget": 0.75}
    multiplier = tier_multipliers.get(tier_pref, 1.0)

    out = []
    for i in range(num):
        base_size  = round((bill / 25) * (1 + increase / 100) * (1 + i * 0.15), 1)
        prop_id    = 9000 + seed_hash + i + 1
        low_price  = int(base_size * 1100 * multiplier)
        high_price = int(base_size * 1450 * multiplier)
        monthly_sav = round(bill * 0.8, 2)
        out.append({
            "proposal_id":               prop_id,
            "proposal_name":             f"Option {i+1} – {segment} Solar Plan",
            "system_size_kw":            base_size,
            "monthly_savings":           monthly_sav,
            "estimated_yearly_savings":  round(monthly_sav * 12, 2),
            "approx_price":              f"${low_price:,} – ${high_price:,}",
            "payback_years":             round(((low_price + high_price) / 2) / max(monthly_sav * 12, 1), 1),
            "city":                      city,
            "status":                    "New",
            "date_created":              str(date.today()),
            "inverter_brand":            brand_pref or tier_pref or "Best Match",
            "module_brand":              "Best Match",
        })
    return out


# ─────────────────────────────────────────────
# TICKET HELPERS
# ─────────────────────────────────────────────

def next_ticket_id() -> int:
    if not tickets_df.empty and "ticket_id" in tickets_df.columns:
        try:
            return int(tickets_df["ticket_id"].max()) + 1
        except Exception:
            pass
    return 1001


def save_new_ticket(ticket: dict):
    """Append a new ticket row to data/new_tickets.csv."""
    path = os.path.join(DATA_DIR, "new_tickets.csv")
    row  = pd.DataFrame([ticket])
    if os.path.exists(path):
        row.to_csv(path, mode="a", header=False, index=False)
    else:
        row.to_csv(path, mode="w", header=True, index=False)
