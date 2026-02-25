"""
main.py
-------
Interactive terminal runner for the SunBun LangGraph assistant.

How interrupt() works with LangGraph:
  1. graph.invoke(state, config) runs until it hits an interrupt() call.
  2. The graph saves a checkpoint and returns.
  3. We read the interrupt payload from snapshot.tasks[0].interrupts[0].value
  4. We display the message/buttons to the user and collect their answer.
  5. We resume with graph.invoke(Command(resume=answer), config).
  6. Repeat until snapshot.next == () (graph has reached END).
"""

import uuid
from langgraph.types import Command
from graph import compile_graph
from state import SunBunState

graph = compile_graph()


def run_session():
    # Unique thread_id per session so checkpointer tracks the right snapshot
    thread_id = f"sunbun-session-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}

    initial_state: SunBunState = {
        "session_id": thread_id,
        "support_type": None,
        "id_type_choice": None,
        "user_identifier": None,
        "user_otp_input": None,
        "auth_attempts": 0,
        "auth_verified": False,
        "in_db": None,
        "lookup_attempts": 0,
        "customer_id": None,
        "customer_name": None,
        "location": None,
        "site_id": None,
        "has_proposals": None,
        "issue_flag": None,
        "issue_text": None,
        "recommended_action_text": None,
        "metrics": None,
        "wants_escalation": None,
        "selected_issue": None,
        "description": None,
        "photos": [],
        "ticket_id": None,
        "nps_score": None,
        "nps_feedback": None,
        "wants_live_chat": None,
        "external_data": None,
        "sales_profile": None,
        "proposals": [],
        "chosen_proposal_id": None,
        "contact_preference": None,
        "display_message": "",
        "display_buttons": [],
    }

    print("\n" + "═" * 60)
    print("         SunBun Solar Assistant  (Week 1 Demo)")
    print("═" * 60)

    # ── First invoke: graph runs until the first interrupt() ──────────────────
    graph.invoke(initial_state, config=config)

    # ── Main loop: read interrupt payload → show to user → resume ─────────────
    while True:
        snapshot = graph.get_state(config)

        # Graph finished when there are no pending next nodes
        if not snapshot.next:
            print("\n" + "─" * 60)
            print("  Session ended. Thank you for using SunBun Assistant!")
            print("─" * 60 + "\n")
            break

        # Safety check: if no interrupt is pending something went wrong
        if not snapshot.tasks or not snapshot.tasks[0].interrupts:
            print("[Debug] No interrupt found but graph not done. Ending.")
            break

        payload = snapshot.tasks[0].interrupts[0].value

        # Display the assistant message
        print(f"\n{'─'*60}")
        print(f"Assistant: {payload['display_message']}")
        buttons = payload.get("display_buttons", [])
        if buttons:
            print(f"\n  Options:")
            for i, btn in enumerate(buttons, 1):
                print(f"    [{i}] {btn}")
            print()

        # Collect user input
        user_answer = input("Your answer: ").strip()

        # If user typed a number corresponding to a button, resolve it
        if buttons and user_answer.isdigit():
            idx = int(user_answer) - 1
            if 0 <= idx < len(buttons):
                user_answer = buttons[idx]

        # Resume the graph
        graph.invoke(Command(resume=user_answer), config=config)


if __name__ == "__main__":
    run_session()
