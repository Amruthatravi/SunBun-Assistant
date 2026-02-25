"""
state.py
--------
Single source of truth for all state that flows through the SunBun graph.
Every node reads from and writes to this object only — no hidden globals.
"""

from typing import TypedDict, Optional, Literal, List


class SunBunState(TypedDict):
    # ── Session ──────────────────────────────────────────────────────────────
    session_id: str

    # ── Routing ──────────────────────────────────────────────────────────────
    support_type: Optional[Literal["sales", "service"]]

    # ── Auth ─────────────────────────────────────────────────────────────────
    id_type_choice: Optional[Literal["email", "phone"]]   # which identifier user chose
    user_identifier: Optional[str]                        # email or phone value
    user_otp_input: Optional[str]                         # OTP typed by user
    auth_attempts: int                                    # OTP attempt counter (max 3)
    auth_verified: bool                                   # True after correct OTP

    # ── Customer DB lookup ───────────────────────────────────────────────────
    in_db: Optional[bool]           # True=found, False=not found, None=not checked
    lookup_attempts: int            # how many times identifier lookup was tried
    customer_id: Optional[str]
    customer_name: Optional[str]
    location: Optional[str]
    site_id: Optional[int]
    has_proposals: Optional[bool]   # True if proposals exist for this customer

    # ── Service flow ─────────────────────────────────────────────────────────
    issue_flag: Optional[bool]
    issue_text: Optional[str]
    recommended_action_text: Optional[str]
    metrics: Optional[dict]         # {"avg_cloudiness": X, "total_prod": Y, "perf_score": Z}
    wants_escalation: Optional[bool]
    selected_issue: Optional[str]
    description: Optional[str]
    photos: List[str]               # list of file paths / "none"
    ticket_id: Optional[str]
    nps_score: Optional[int]
    nps_feedback: Optional[str]
    wants_live_chat: Optional[bool]

    # ── External / non-DB service ────────────────────────────────────────────
    external_data: Optional[dict]   # system_size, inverter_brand, install_year, etc.

    # ── Sales flow ───────────────────────────────────────────────────────────
    sales_profile: Optional[dict]   # name, postal, city, segment, bill, growth%, prefs
    proposals: List[dict]           # list of generated proposal summaries
    chosen_proposal_id: Optional[str]
    contact_preference: Optional[Literal["call", "chat"]]

    # ── UI ───────────────────────────────────────────────────────────────────
    display_message: str
    display_buttons: List[str]
