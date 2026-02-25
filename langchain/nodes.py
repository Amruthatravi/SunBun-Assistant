"""
nodes.py
--------
All deterministic LangGraph nodes for the SunBun assistant.

Each node:
  - Takes SunBunState as input.
  - Returns a PARTIAL dict of keys it changed (LangGraph merges automatically).
  - Uses interrupt() to pause for user input.
  - Never calls an LLM — all logic is rule-based / CSV-driven.
"""

from langgraph.types import interrupt
from state import SunBunState
import data_loader as db


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 – ENTRY
# ═══════════════════════════════════════════════════════════════════════════════

def entry_node(state: SunBunState) -> dict:
    """
    First node: greet the visitor and capture support_type.
    Greets by name if customer_name is already known (cookie / query param),
    otherwise generically.
    """
    name = state.get("customer_name") or "there"
    greeting = f"Hi {name}! " if state.get("customer_name") else "Hello! "

    answer = interrupt({
        "display_message": greeting + "Welcome to SunBun. How can we help you today?",
        "display_buttons": [
            "Sales Support – I'm interested in buying / upgrading a system",
            "Service Support – I need help with an existing or new system",
        ],
    })

    support = "sales" if "sales" in answer.lower() else "service"
    return {"support_type": support}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 – AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════

def auth_collect_contact(state: SunBunState) -> dict:
    """Ask user to choose email or phone, then collect the identifier."""
    id_choice = interrupt({
        "display_message": "Please continue with either your registered email or phone number.",
        "display_buttons": ["Use email", "Use phone"],
    })
    id_type = "email" if "email" in id_choice.lower() else "phone"

    prompt = "Enter your email address:" if id_type == "email" else "Enter your mobile number:"
    identifier = interrupt({
        "display_message": prompt,
        "display_buttons": [],
    })

    return {
        "id_type_choice": id_type,
        "user_identifier": identifier.strip(),
        "auth_attempts": 0,
        "auth_verified": False,
    }


def auth_send_otp(state: SunBunState) -> dict:
    """
    Simulate OTP dispatch.
    In reality this would call an SMS/email gateway.
    Here we just inform the user and let verify_otp do the check.
    """
    channel = "email" if state.get("id_type_choice") == "email" else "SMS"
    return {
        "display_message": (
            f"We're sending you a one-time code. "
            f"Please check your {channel} and enter the code here."
        ),
        "display_buttons": [],
    }


def auth_verify_otp(state: SunBunState) -> dict:
    """
    Collect OTP input and verify against CSV.
    Handles up to 3 attempts; on 3rd failure offers Retry / Exit.
    """
    attempts = state.get("auth_attempts", 0)

    otp_input = interrupt({
        "display_message": f"Enter the 6-digit code you received (Attempt {attempts + 1}/3):",
        "display_buttons": [],
    })

    identifier = state.get("user_identifier", "")
    attempts += 1

    # Look up valid OTPs from both CSVs
    valid_email = (
        db.email_otp_df[db.email_otp_df["email"] == identifier]["otp"]
        .astype(str).tolist()
        if not db.email_otp_df.empty else []
    )
    valid_sms = (
        db.sms_otp_df[db.sms_otp_df["phone"] == identifier]["otp"]
        .astype(str).tolist()
        if not db.sms_otp_df.empty else []
    )
    all_valid = valid_email + valid_sms

    if otp_input.strip() in all_valid:
        return {
            "user_otp_input": otp_input,
            "auth_verified": True,
            "auth_attempts": attempts,
        }

    # Wrong OTP
    if attempts >= 3:
        retry_choice = interrupt({
            "display_message": (
                "We couldn't verify your identity right now. "
                "Would you like to try again or exit?"
            ),
            "display_buttons": ["Retry authentication", "Exit"],
        })
        if "retry" in retry_choice.lower():
            # Signal the router to restart auth from contact collection
            return {
                "user_otp_input": otp_input,
                "auth_verified": False,
                "auth_attempts": 0,          # reset → router sends back to auth_collect_contact
                "user_identifier": None,
            }
        else:
            return {
                "user_otp_input": otp_input,
                "auth_verified": False,
                "auth_attempts": attempts,   # keep at 3 → router goes to END
            }

    # Still have attempts left — router will loop back to verify_otp
    print(f"⚠️  That code doesn't look right. (Attempt {attempts}/3)")
    return {
        "user_otp_input": otp_input,
        "auth_verified": False,
        "auth_attempts": attempts,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 – CUSTOMER LOOKUP
# ═══════════════════════════════════════════════════════════════════════════════

def customer_lookup(state: SunBunState) -> dict:
    """
    Look up the identifier in customers.csv.
    Sets in_db, customer_id, customer_name, location, site_id, has_proposals.
    On first failure offers 'Try again'; second failure routes to external path.
    """
    identifier = state.get("user_identifier", "")
    lookup_attempts = state.get("lookup_attempts", 0) + 1

    import pandas as pd
    import functools, operator
    match = pd.DataFrame()
    if not db.customers_df.empty:
        conditions = []
        if "email" in db.customers_df.columns:
            conditions.append(db.customers_df["email"] == identifier)
        if "phone" in db.customers_df.columns:
            conditions.append(db.customers_df["phone"] == identifier)
        if conditions:
            match = db.customers_df[functools.reduce(operator.or_, conditions)]

    if not match.empty:
        row = match.iloc[0]
        cid = str(row.get("customer_id", ""))

        # Check if this customer has proposals
        has_props = False
        if not db.proposals_df.empty and "customer_id" in db.proposals_df.columns:
            has_props = not db.proposals_df[
                db.proposals_df["customer_id"].astype(str) == cid
            ].empty

        print(f"✅ Record found for {identifier}.")
        return {
            "in_db": True,
            "lookup_attempts": lookup_attempts,
            "customer_id": cid,
            "customer_name": str(row.get("name", "")),
            "location": str(row.get("location", "")),
            "site_id": int(row.get("site_id", 0)) if row.get("site_id") else None,
            "has_proposals": has_props,
        }

    # Not found
    if lookup_attempts == 1:
        retry = interrupt({
            "display_message": (
                "We couldn't find a system in our records matching this email/phone.\n"
                "If you are an existing SunBun customer, please make sure you're using "
                "the same email or phone number that you used for your monitoring portal."
                "\n\nWould you like to try a different email/phone?"
            ),
            "display_buttons": ["Try again", "No, continue anyway"],
        })
        if "try" in retry.lower():
            return {
                "in_db": None,              # → router loops back to auth_collect_contact
                "lookup_attempts": lookup_attempts,
                "user_identifier": None,
            }

    # Second failure or user chose "continue anyway"
    return {
        "in_db": False,
        "lookup_attempts": lookup_attempts,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 – SERVICE SUPPORT (existing customer in DB)
# ═══════════════════════════════════════════════════════════════════════════════

def service_greet(state: SunBunState) -> dict:
    """Personalized welcome for found customers before system check."""
    name = state.get("customer_name", "")
    location = state.get("location", "")
    print(f"\n✅ Hi {name} from {location}, welcome back to SunBun.")
    return {}


def service_status_check(state: SunBunState) -> dict:
    """
    Core monitoring node.
    Priority 1 – check site_issues.csv for an active flag.
    Priority 2 – compute weekly averages from weekly_metrics.csv.
    Returns metrics and a user-facing message via interrupt (ask happy/need help).
    """
    site_id = state.get("site_id")

    # ── Priority 1: active issue flag ────────────────────────────────────────
    issue_flag = False
    issue_text = None
    recommended_action_text = None

    if not db.site_issues_df.empty and "site_id" in db.site_issues_df.columns:
        issue_row = db.site_issues_df[db.site_issues_df["site_id"] == site_id]
        if not issue_row.empty:
            row = issue_row.iloc[0]
            # Coerce to plain Python bool to avoid numpy bool issues
            issue_flag = bool(row.get("issue_flag", False))
            if issue_flag:
                issue_text = str(row.get("issue_text", "Unknown issue"))
                recommended_action_text = str(row.get("recommended_action_text", "Contact support"))

    # ── Priority 2: weekly metrics ────────────────────────────────────────────
    avg_cloudiness = 0
    total_prod = 0.0
    perf_score = 100

    if not issue_flag:
        # Try weekly_metrics.csv first, fall back to sites.csv simulation
        if not db.weekly_metrics_df.empty and "site_id" in db.weekly_metrics_df.columns:
            wm = db.weekly_metrics_df[db.weekly_metrics_df["site_id"] == site_id]
            if not wm.empty:
                avg_cloudiness = int(wm["cloudiness"].mean()) if "cloudiness" in wm.columns else 0
                total_prod = round(wm["daily_production_kwh"].sum(), 1) if "daily_production_kwh" in wm.columns else 0.0
                perf_score = int(wm["performance_score"].mean()) if "performance_score" in wm.columns else 100
        else:
            # Deterministic simulation from site_id (no randomness)
            if not db.sites_df.empty and site_id:
                site_row = db.sites_df[db.sites_df["site_id"] == site_id]
                if not site_row.empty:
                    kw = float(site_row.iloc[0].get("system_size_kw", 5))
                    avg_cloudiness = (site_id * 7) % 100
                    perf_score = 100 - ((site_id % 5) * 4)
                    total_prod = round(kw * 4.2 * 7 * (perf_score / 100), 1)

    metrics = {
        "avg_cloudiness": avg_cloudiness,
        "total_prod_kwh": total_prod,
        "performance_score": perf_score,
    }

    # ── Build assistant message ───────────────────────────────────────────────
    print("\nAssistant: Let me quickly check the current status of your solar system in our monitoring platform.")

    if issue_flag:
        system_msg = (
            f"We are currently seeing an issue on your system.\n"
            f"Issue: {issue_text}.\n"
            f"Recommended action: {recommended_action_text}."
        )
    elif avg_cloudiness > 60:
        system_msg = (
            f"Your system does not show any active faults. However, the last week has been "
            f"unusually cloudy ({avg_cloudiness}% average) at your location, which is likely why "
            f"your production has been lower than normal. It should auto-correct as weather improves."
        )
    elif perf_score >= 90:
        system_msg = (
            f"Your system appears to be performing normally. "
            f"Last week's total production was {total_prod} kWh."
        )
    else:
        system_msg = (
            f"Your system appears to be performing normally. "
            f"Last week's total production was {total_prod} kWh.\n"
            f"We see a slight underperformance trend, but nothing critical yet. "
            f"We'll continue monitoring it."
        )

    answer = interrupt({
        "display_message": system_msg + "\n\nDoes this answer your question, or would you like to speak to support?",
        "display_buttons": ["I'm happy with this explanation", "I still need help"],
    })

    wants_escalation = "still need help" in answer.lower()
    return {
        "issue_flag": issue_flag,
        "issue_text": issue_text,
        "recommended_action_text": recommended_action_text,
        "metrics": metrics,
        "wants_escalation": wants_escalation,
    }


def service_nps_and_close(state: SunBunState) -> dict:
    """
    Auto-resolution path.
    Creates a resolved ticket, collects NPS + free text feedback, then closes.
    """
    ticket_id = db.get_next_ticket_id()
    print(f"\nAssistant: Great, we'll log that your query has been resolved. (Ticket: {ticket_id})")

    nps_raw = interrupt({
        "display_message": "On a scale of 1 to 10 (10 being excellent), how satisfied are you with the support you received just now?",
        "display_buttons": ["1","2","3","4","5","6","7","8","9","10"],
    })

    feedback = interrupt({
        "display_message": "Anything else you'd like to share about your experience?",
        "display_buttons": [],
    })

    print("\nAssistant: Thank you. Your feedback helps us improve. Have a great day!")

    try:
        nps = int(nps_raw.strip())
    except Exception:
        nps = 0

    return {
        "ticket_id": ticket_id,
        "nps_score": nps,
        "nps_feedback": feedback,
    }


def service_issue_capture(state: SunBunState) -> dict:
    """
    Escalation path — collect issue type, description, and photo evidence.
    """
    category = interrupt({
        "display_message": "Sorry to hear that. Let's understand the issue in a bit more detail.\nPlease select an issue type:",
        "display_buttons": [
            "Production Issue",
            "System Not Working",
            "Communication Loss",
            "Battery Failure",
            "Inverter Failure",
            "Others",
        ],
    })

    description = interrupt({
        "display_message": "Please describe the issue in your own words:",
        "display_buttons": [],
    })

    photos_raw = interrupt({
        "display_message": (
            "If possible, please upload photos or screenshots that show what you're seeing "
            "(inverter screen, app screenshots, physical damage, etc.).\n"
            "Type file paths separated by commas, or 'none' to skip."
        ),
        "display_buttons": ["none"],
    })

    photos = [] if photos_raw.strip().lower() == "none" else [p.strip() for p in photos_raw.split(",")]

    return {
        "selected_issue": category,
        "description": description,
        "photos": photos,
    }


def service_ticket_create(state: SunBunState) -> dict:
    """
    Creates service ticket (in-memory simulation) and checks agent availability.
    If agent online → offer live chat. Otherwise → ticket only.
    """
    ticket_id = db.get_next_ticket_id()
    agent_online = db.is_service_agent_online()

    if agent_online:
        chat_answer = interrupt({
            "display_message": "We have a service executive available right now. Would you like to start a live chat?",
            "display_buttons": ["Yes, start live chat", "No, just create a ticket"],
        })
        wants_chat = "yes" in chat_answer.lower()
    else:
        wants_chat = False
        print("\nAssistant: Our service team is currently offline. I'll create a ticket with all the details you've shared so we can follow up.")

    print(f"\n✅ Your service ticket has been created. Ticket number: {ticket_id}. Our team will reach out to you shortly.")

    return {
        "ticket_id": ticket_id,
        "wants_live_chat": wants_chat,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 – SERVICE SUPPORT (external / non-DB path)
# ═══════════════════════════════════════════════════════════════════════════════

def service_external_collect(state: SunBunState) -> dict:
    """
    Collect system details for a non-SunBun or unregistered customer.
    """
    print("\nAssistant: It looks like we don't have your system in our records. We can still help, but we'll need a few details about your setup.")

    system_size = interrupt({
        "display_message": "Approximate system size (kWp):",
        "display_buttons": [],
    })
    inverter_brand = interrupt({
        "display_message": "Inverter brand / model:",
        "display_buttons": [],
    })
    install_year = interrupt({
        "display_message": "Year of installation:",
        "display_buttons": [],
    })
    monitoring_active = interrupt({
        "display_message": "Is online monitoring active?",
        "display_buttons": ["Yes", "No"],
    })
    installer_name = interrupt({
        "display_message": "Who installed your system? (Type the installer's name, or 'Don't remember')",
        "display_buttons": [],
    })

    # Issue details
    issue_category = interrupt({
        "display_message": "What is the issue type?",
        "display_buttons": [
            "Production Issue", "System Not Working", "Communication Loss",
            "Battery Failure", "Inverter Failure", "Others",
        ],
    })
    issue_description = interrupt({
        "display_message": "Please describe the issue in your own words:",
        "display_buttons": [],
    })
    photos_raw = interrupt({
        "display_message": "Upload photos or screenshots if available (comma-separated paths, or 'none'):",
        "display_buttons": ["none"],
    })
    photos = [] if photos_raw.strip().lower() == "none" else [p.strip() for p in photos_raw.split(",")]

    external_data = {
        "system_size_kwp": system_size,
        "inverter_brand": inverter_brand,
        "install_year": install_year,
        "monitoring_active": monitoring_active,
        "installer_name": installer_name,
        "issue_category": issue_category,
        "description": issue_description,
        "photos": photos,
    }

    return {
        "external_data": external_data,
        "selected_issue": issue_category,
        "description": issue_description,
        "photos": photos,
    }


def service_external_ticket(state: SunBunState) -> dict:
    """
    Create ticket / hand off for non-DB customers.
    """
    ticket_id = db.get_next_ticket_id()
    agent_online = db.is_service_agent_online()

    if agent_online:
        chat_answer = interrupt({
            "display_message": "We have a service executive available. Would you like to chat with them now to discuss your issue?",
            "display_buttons": ["Yes, chat now", "No, just raise a ticket"],
        })
        wants_chat = "yes" in chat_answer.lower()
        if wants_chat:
            print("\nAssistant: Connecting you to a service executive now. Please wait…")
    else:
        wants_chat = False
        print("\nAssistant: Our service team is currently offline. I'll raise a ticket for you with all these details.")

    print(f"\n✅ We've created a ticket for you: {ticket_id}. Our team will contact you to discuss next steps.")

    return {
        "ticket_id": ticket_id,
        "wants_live_chat": wants_chat,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 – SALES SUPPORT (existing customer in DB)
# ═══════════════════════════════════════════════════════════════════════════════

def sales_greet_existing(state: SunBunState) -> dict:
    """Greet known sales customer and show their proposals if any."""
    name = state.get("customer_name", "")
    has_props = state.get("has_proposals", False)

    if has_props:
        answer = interrupt({
            "display_message": (
                f"Hi {name}, how can we help with your solar plans today?\n"
                f"We see that we've previously shared one or more proposals with you."
            ),
            "display_buttons": ["Review old proposals", "Create new proposals"],
        })
        return {"display_message": answer}   # router uses has_proposals + this answer

    print(f"\nAssistant: Hi {name}, how can we help with your solar plans today?")
    return {}


def sales_review_proposals(state: SunBunState) -> dict:
    """
    Fetch and display existing proposals. Let customer pick one or create new.
    """
    customer_id = state.get("customer_id", "")
    props = []

    if not db.proposals_df.empty and "customer_id" in db.proposals_df.columns:
        customer_props = db.proposals_df[
            db.proposals_df["customer_id"].astype(str) == str(customer_id)
        ]
        for _, row in customer_props.iterrows():
            props.append({
                "proposal_id": str(row.get("proposal_id", "")),
                "name": str(row.get("proposal_name", "Proposal")),
                "price": str(row.get("approx_price", "N/A")),
                "yearly_savings": str(row.get("yearly_savings", "N/A")),
                "date_created": str(row.get("date_created", "N/A")),
                "status": str(row.get("status", "N/A")),
            })

    if not props:
        print("\nAssistant: No old proposals found. Let's create new ones!")
        return {"proposals": []}

    # Display proposals as text cards
    cards = "\n\n".join([
        f"📋 {p['name']}\n"
        f"   Price: {p['price']} | Savings: {p['yearly_savings']}/yr\n"
        f"   Created: {p['date_created']} | Status: {p['status']}"
        for p in props
    ])

    prop_names = [p["name"] for p in props] + ["Create new proposals"]

    answer = interrupt({
        "display_message": f"Here are your existing proposals:\n\n{cards}\n\nWould you like to proceed with any of these, or generate new options?",
        "display_buttons": prop_names,
    })

    if "create new" in answer.lower() or "new" in answer.lower():
        return {"proposals": props}

    # User selected an existing proposal
    chosen = next((p for p in props if p["name"].lower() in answer.lower()), props[0])
    return {
        "proposals": props,
        "chosen_proposal_id": chosen["proposal_id"],
    }


def sales_info_capture(state: SunBunState) -> dict:
    """
    Collect all information needed to generate new proposals.
    Works for both known and unknown customers.
    """
    # Pre-fill name if known
    known_name = state.get("customer_name", "")
    if not known_name:
        name = interrupt({
            "display_message": "What is your name?",
            "display_buttons": [],
        })
    else:
        name = known_name

    postal = interrupt({
        "display_message": "What is your postal code and city? (e.g. 600001 Chennai)",
        "display_buttons": [],
    })

    # Collect complementary contact
    id_type = state.get("id_type_choice")
    if id_type == "phone":
        contact_extra = interrupt({
            "display_message": "Please share your email address for proposal delivery:",
            "display_buttons": [],
        })
    else:
        contact_extra = interrupt({
            "display_message": "Please share your phone number:",
            "display_buttons": [],
        })

    segment = interrupt({
        "display_message": "Are you a Residential, Commercial, or Industrial customer?",
        "display_buttons": ["Residential", "Commercial", "Industrial"],
    })

    bill = interrupt({
        "display_message": "What is your average monthly electricity bill (in your currency)?",
        "display_buttons": [],
    })

    growth = interrupt({
        "display_message": "By what percentage do you expect your electricity consumption to increase in the next few years? (e.g. 10 for 10%, due to EV, heating, new loads)",
        "display_buttons": [],
    })

    num_options = interrupt({
        "display_message": "How many solution options would you like to evaluate right now?",
        "display_buttons": ["1", "2", "3"],
    })

    brand_pref = interrupt({
        "display_message": "Do you have any brand preferences?\nInverters: Enphase, SolarEdge, Sungrow, GoodWe\nModules: Jinko, Trina, Waaree\n(Type preferences or 'none')",
        "display_buttons": ["none"],
    })

    tier = "standard"
    if brand_pref.strip().lower() == "none":
        tier = interrupt({
            "display_message": "Would you prefer Premium, Standard, or Budget options?",
            "display_buttons": ["Premium", "Standard", "Budget"],
        })

    sales_profile = {
        "name": name,
        "postal_city": postal,
        "contact_extra": contact_extra,
        "segment": segment,
        "monthly_bill": bill,
        "growth_pct": growth,
        "num_options": num_options,
        "brand_preference": brand_pref,
        "tier": tier,
    }

    return {"sales_profile": sales_profile}


def sales_proposal_generate(state: SunBunState) -> dict:
    """
    Deterministic proposal generation.
    Uses component_info.csv + proposal_template.csv where available,
    otherwise applies rule-based sizing from monthly bill input.
    Same inputs → same outputs (no LLM).
    """
    print("\nAssistant: Give us a moment while we design the best options based on your requirements…")

    profile = state.get("sales_profile", {})
    bill_str = str(profile.get("monthly_bill", "0")).replace(",", "").replace("₹", "").replace("$", "").strip()
    try:
        monthly_bill = float(bill_str)
    except Exception:
        monthly_bill = 5000.0

    growth_str = str(profile.get("growth_pct", "0")).replace("%", "").strip()
    try:
        growth_pct = float(growth_str) / 100
    except Exception:
        growth_pct = 0.1

    segment = profile.get("segment", "Residential").lower()
    tier = profile.get("tier", "standard").lower()
    try:
        num_options = int(str(profile.get("num_options", "1")))
    except Exception:
        num_options = 1
    num_options = min(max(num_options, 1), 3)

    # ── Sizing rules ──────────────────────────────────────────────────────────
    # Approximate: 1 kW system generates ~120 kWh/month in India
    # Monthly consumption ≈ bill / avg_tariff (₹8/unit assumed)
    tariff = 8.0
    monthly_kwh = monthly_bill / tariff
    adjusted_kwh = monthly_kwh * (1 + growth_pct)
    base_kw = round(adjusted_kwh / 120, 1)
    if segment == "commercial":
        base_kw = round(base_kw * 1.2, 1)
    elif segment == "industrial":
        base_kw = round(base_kw * 1.5, 1)
    base_kw = max(base_kw, 1.0)

    # ── Component selection ───────────────────────────────────────────────────
    tier_map = {
        "premium":  {"inverter": "Enphase", "module": "Jinko",  "price_per_kw": 65000},
        "standard": {"inverter": "GoodWe",  "module": "Trina",  "price_per_kw": 55000},
        "budget":   {"inverter": "Sungrow", "module": "Waaree", "price_per_kw": 45000},
    }
    brand_pref = profile.get("brand_preference", "none").lower()
    if brand_pref != "none":
        chosen_tier = tier_map["premium"]   # explicit brand → premium pricing as proxy
    else:
        chosen_tier = tier_map.get(tier, tier_map["standard"])

    proposals = []
    for i in range(num_options):
        # Each option slightly different size/price for variety
        factor = 1.0 + (i * 0.1)
        kw = round(base_kw * factor, 1)
        price = round(kw * chosen_tier["price_per_kw"], -3)   # round to nearest 1000
        annual_prod = round(kw * 1440, 0)                     # ~1440 kWh/kW/year
        annual_savings = round(annual_prod * tariff, -2)
        payback = round(price / annual_savings, 1)
        proposal_id = f"PROP-{state.get('customer_id', 'NEW')}-{i+1:02d}"

        proposals.append({
            "proposal_id": proposal_id,
            "name": f"{kw} kW {profile.get('segment','Residential')} – {chosen_tier['inverter']} + {chosen_tier['module']}",
            "system_size_kw": kw,
            "inverter": chosen_tier["inverter"],
            "module": chosen_tier["module"],
            "approx_price": f"₹{price:,.0f}",
            "estimated_annual_production_kwh": annual_prod,
            "estimated_annual_savings": f"₹{annual_savings:,.0f}",
            "payback_years": payback,
            "view_link": f"https://sunbun.in/proposals/{proposal_id}",
        })

    return {"proposals": proposals}


def sales_proposal_confirm(state: SunBunState) -> dict:
    """
    Show proposals to user, let them pick one, then handle Inside Sales handoff.
    """
    proposals = state.get("proposals", [])

    # Build display
    cards = "\n\n".join([
        f"🌞 Option {i+1}: {p['name']}\n"
        f"   Size: {p['system_size_kw']} kW | Price: {p['approx_price']}\n"
        f"   Annual savings: {p['estimated_annual_savings']} | Payback: {p['payback_years']} yrs\n"
        f"   🔗 {p['view_link']}"
        for i, p in enumerate(proposals)
    ])

    option_labels = [f"Select Option {i+1}: {p['name']}" for i, p in enumerate(proposals)]

    choice = interrupt({
        "display_message": f"Here are your customised proposals:\n\n{cards}\n\nPlease select the option you'd like to proceed with:",
        "display_buttons": option_labels,
    })

    # Match chosen proposal
    chosen = proposals[0]
    for i, p in enumerate(proposals):
        if str(i+1) in choice or p["name"].lower() in choice.lower():
            chosen = p
            break

    print(f"\nAssistant: Thank you for your interest in the {chosen['name']} option.")

    # ── Inside Sales handoff ──────────────────────────────────────────────────
    agent_online = db.is_sales_agent_online()
    contact_preference = None

    if agent_online:
        contact_pref = interrupt({
            "display_message": "Would you prefer to speak with our sales representative via call or chat?",
            "display_buttons": ["Call", "Chat"],
        })
        contact_preference = contact_pref.lower()
        if contact_preference == "chat":
            print(f"\nAssistant: Connecting you to a sales representative now with your proposal details…")
        else:
            print(f"\nAssistant: Perfect. We'll have a sales representative call you about the {chosen['name']} proposal within 1 hour.")
    else:
        print("\nAssistant: Our sales team is currently unavailable for live conversations, but we've logged your interest.")
        print("You'll receive a call or email from our team soon with the next steps.")

    print("\nAssistant: Thank you for considering SunBun. We'll be in touch shortly.")

    return {
        "chosen_proposal_id": chosen["proposal_id"],
        "contact_preference": contact_preference,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 – TERMINAL NODES
# ═══════════════════════════════════════════════════════════════════════════════

def auth_exit_node(state: SunBunState) -> dict:
    """Called when user exits after 3 failed OTP attempts."""
    print("\n❌ Authentication failed after 3 attempts. Please contact SunBun support directly. Goodbye!")
    return {}


def sales_not_in_db_intro(state: SunBunState) -> dict:
    """Intro message for new prospect going into sales flow."""
    print(
        "\nAssistant: We couldn't find an existing SunBun system under your details. "
        "Let's collect some information to prepare a customised solar proposal for you."
    )
    return {}
