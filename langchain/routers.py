"""
routers.py
----------
All conditional-edge functions for the SunBun LangGraph.

Each router receives the current SunBunState and returns a string key
that maps to the next node name.
"""

from typing import Literal
from state import SunBunState


def route_support_type(state: SunBunState) -> Literal["service_greet", "sales_check_proposals"]:
    """After customer_lookup succeeds: branch Sales vs Service."""
    if state.get("support_type") == "sales":
        return "sales_check_proposals"
    return "service_greet"


def route_after_otp(state: SunBunState) -> Literal[
    "customer_lookup",
    "auth_verify_otp",
    "auth_exit_node",
]:
    """
    After auth_verify_otp runs:
    - Correct OTP and auth_verified=True  → customer_lookup
    - Wrong OTP, attempts < 3             → loop back to auth_verify_otp
    - 3 failed attempts, user chose Exit  → auth_exit_node
    - 3 failed attempts, user chose Retry → auth_collect_contact (handled via None identifier)
    """
    if state.get("auth_verified"):
        return "customer_lookup"
    attempts = state.get("auth_attempts", 0)
    identifier = state.get("user_identifier")
    if attempts >= 3 and identifier is None:
        # User chose "Retry" → restart auth from contact collection
        return "auth_collect_contact"
    if attempts >= 3:
        return "auth_exit_node"
    return "auth_verify_otp"


def route_after_lookup(state: SunBunState) -> Literal[
    "service_greet",
    "sales_check_proposals",
    "service_external_collect",
    "sales_not_in_db_intro",
    "auth_collect_contact",
]:
    """
    After customer_lookup:
    - in_db=True  → personalized branch (service or sales)
    - in_db=None  → user wants to try again → re-collect contact
    - in_db=False → external/non-DB path
    """
    in_db = state.get("in_db")
    support = state.get("support_type")

    if in_db is True:
        return "service_greet" if support == "service" else "sales_check_proposals"
    if in_db is None:
        return "auth_collect_contact"
    # in_db is False
    return "service_external_collect" if support == "service" else "sales_not_in_db_intro"


def route_service_resolution(state: SunBunState) -> Literal[
    "service_issue_capture",
    "service_nps_and_close",
]:
    """After system_status_check: escalate or auto-resolve."""
    if state.get("wants_escalation"):
        return "service_issue_capture"
    return "service_nps_and_close"


def route_sales_proposals(state: SunBunState) -> Literal[
    "sales_review_proposals",
    "sales_info_capture",
]:
    """
    If customer has prior proposals, offer to review them.
    Otherwise go straight to collecting new sales info.
    """
    if state.get("has_proposals"):
        return "sales_review_proposals"
    return "sales_info_capture"


def route_after_proposal_review(state: SunBunState) -> Literal[
    "sales_proposal_confirm",
    "sales_info_capture",
]:
    """
    If user selected an existing proposal, go confirm it.
    If they want new ones, collect fresh sales info.
    """
    if state.get("chosen_proposal_id"):
        return "sales_proposal_confirm"
    return "sales_info_capture"
