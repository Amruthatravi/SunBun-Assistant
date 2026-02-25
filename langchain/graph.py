"""
graph.py
--------
Assembles the complete SunBun LangGraph state machine.

Graph topology (ASCII):

  START
    │
    ▼
  entry_node ──(support_type captured)──►
    │
    ▼
  auth_collect_contact ◄─────────────────────────────┐
    │                                                 │
    ▼                                                 │
  auth_send_otp                                       │
    │                                                 │ retry (user_identifier=None, attempts reset)
    ▼                                                 │
  auth_verify_otp ◄──────────────────────────────┐   │
    │                                             │   │
    ├─ auth_verified=True ──► customer_lookup     │   │
    ├─ attempts<3 ───────────────────────────────►┘   │
    ├─ attempts>=3, Retry ───────────────────────────►┘
    └─ attempts>=3, Exit ──► auth_exit_node ──► END
                                   │
             customer_lookup ◄─────┘
                │
                ├─ in_db=True, service  ──► service_greet ──► service_status_check
                │                              │
                │                    ┌──────────┴──────────────────┐
                │                    │                             │
                │               wants_escalation=True        wants_escalation=False
                │                    │                             │
                │            service_issue_capture          service_nps_and_close ──► END
                │                    │
                │          service_ticket_create ──► END
                │
                ├─ in_db=True, sales  ──► sales_check_proposals
                │                              │
                │                  ┌───────────┴────────────┐
                │                  │                        │
                │         has_proposals=True        has_proposals=False
                │                  │                        │
                │        sales_review_proposals      sales_info_capture
                │                  │                        │
                │        chosen_proposal_id?                │
                │           yes ──► sales_proposal_confirm  │
                │           no  ──► sales_info_capture ─────┘
                │                                           │
                │                             sales_proposal_generate
                │                                           │
                │                             sales_proposal_confirm ──► END
                │
                ├─ in_db=False, service ──► service_external_collect
                │                               │
                │                    service_external_ticket ──► END
                │
                ├─ in_db=False, sales ──► sales_not_in_db_intro
                │                               │
                │                        sales_info_capture (reuse)
                │                               │
                │                      sales_proposal_generate
                │                               │
                │                      sales_proposal_confirm ──► END
                │
                └─ in_db=None ──► auth_collect_contact (retry loop)
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from state import SunBunState
from nodes import (
    entry_node,
    auth_collect_contact,
    auth_send_otp,
    auth_verify_otp,
    auth_exit_node,
    customer_lookup,
    service_greet,
    service_status_check,
    service_nps_and_close,
    service_issue_capture,
    service_ticket_create,
    service_external_collect,
    service_external_ticket,
    sales_greet_existing,
    sales_review_proposals,
    sales_info_capture,
    sales_proposal_generate,
    sales_proposal_confirm,
    sales_not_in_db_intro,
)
from routers import (
    route_after_otp,
    route_after_lookup,
    route_service_resolution,
    route_sales_proposals,
    route_after_proposal_review,
)


def build_graph() -> StateGraph:
    builder = StateGraph(SunBunState)

    # ── Register nodes ────────────────────────────────────────────────────────
    builder.add_node("entry_node",                entry_node)
    builder.add_node("auth_collect_contact",      auth_collect_contact)
    builder.add_node("auth_send_otp",             auth_send_otp)
    builder.add_node("auth_verify_otp",           auth_verify_otp)
    builder.add_node("auth_exit_node",            auth_exit_node)
    builder.add_node("customer_lookup",           customer_lookup)

    # Service – existing customer
    builder.add_node("service_greet",             service_greet)
    builder.add_node("service_status_check",      service_status_check)
    builder.add_node("service_nps_and_close",     service_nps_and_close)
    builder.add_node("service_issue_capture",     service_issue_capture)
    builder.add_node("service_ticket_create",     service_ticket_create)

    # Service – external / non-DB
    builder.add_node("service_external_collect",  service_external_collect)
    builder.add_node("service_external_ticket",   service_external_ticket)

    # Sales – existing customer
    builder.add_node("sales_check_proposals",     sales_greet_existing)   # greet + route decision captured here
    builder.add_node("sales_review_proposals",    sales_review_proposals)
    builder.add_node("sales_info_capture",        sales_info_capture)
    builder.add_node("sales_proposal_generate",   sales_proposal_generate)
    builder.add_node("sales_proposal_confirm",    sales_proposal_confirm)

    # Sales – new prospect
    builder.add_node("sales_not_in_db_intro",     sales_not_in_db_intro)

    # ── Edges ─────────────────────────────────────────────────────────────────

    # Entry → Auth
    builder.add_edge(START,                        "entry_node")
    builder.add_edge("entry_node",                 "auth_collect_contact")
    builder.add_edge("auth_collect_contact",       "auth_send_otp")
    builder.add_edge("auth_send_otp",              "auth_verify_otp")

    # OTP loop / exit / proceed
    builder.add_conditional_edges("auth_verify_otp", route_after_otp, {
        "customer_lookup":      "customer_lookup",
        "auth_verify_otp":      "auth_verify_otp",      # wrong OTP, retry
        "auth_collect_contact": "auth_collect_contact", # user chose Retry after 3 fails
        "auth_exit_node":       "auth_exit_node",
    })
    builder.add_edge("auth_exit_node", END)

    # Lookup → branch
    builder.add_conditional_edges("customer_lookup", route_after_lookup, {
        "service_greet":             "service_greet",
        "sales_check_proposals":     "sales_check_proposals",
        "service_external_collect":  "service_external_collect",
        "sales_not_in_db_intro":     "sales_not_in_db_intro",
        "auth_collect_contact":      "auth_collect_contact",   # retry with different identifier
    })

    # ── SERVICE – existing ────────────────────────────────────────────────────
    builder.add_edge("service_greet",          "service_status_check")
    builder.add_conditional_edges("service_status_check", route_service_resolution, {
        "service_issue_capture":  "service_issue_capture",
        "service_nps_and_close":  "service_nps_and_close",
    })
    builder.add_edge("service_issue_capture",  "service_ticket_create")
    builder.add_edge("service_ticket_create",  END)
    builder.add_edge("service_nps_and_close",  END)

    # ── SERVICE – external ────────────────────────────────────────────────────
    builder.add_edge("service_external_collect", "service_external_ticket")
    builder.add_edge("service_external_ticket",  END)

    # ── SALES – existing proposals branch ─────────────────────────────────────
    builder.add_conditional_edges("sales_check_proposals", route_sales_proposals, {
        "sales_review_proposals": "sales_review_proposals",
        "sales_info_capture":     "sales_info_capture",
    })
    builder.add_conditional_edges("sales_review_proposals", route_after_proposal_review, {
        "sales_proposal_confirm": "sales_proposal_confirm",
        "sales_info_capture":     "sales_info_capture",
    })

    # ── SALES – new proposals ─────────────────────────────────────────────────
    builder.add_edge("sales_info_capture",        "sales_proposal_generate")
    builder.add_edge("sales_proposal_generate",   "sales_proposal_confirm")
    builder.add_edge("sales_proposal_confirm",    END)

    # ── SALES – new prospect (not in DB) ─────────────────────────────────────
    builder.add_edge("sales_not_in_db_intro",     "sales_info_capture")

    return builder


def compile_graph():
    """Compile the graph with in-memory checkpointing (required for interrupt())."""
    memory = MemorySaver()
    return build_graph().compile(checkpointer=memory)
