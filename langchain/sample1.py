import pandas as pd
import sys

# Load Datasets
customers_df = pd.read_csv("customers.csv")
prospects_df = pd.read_csv("prospects.csv")
email_otp_df = pd.read_csv("email_otp.csv")
sms_otp_df = pd.read_csv("sms_otp.csv") 
site_issues_df = pd.read_csv("site_issues.csv")
weekly_metrics_df = pd.read_csv("weekly_metrics.csv")
agent_avail_df = pd.read_csv("agent_availability.csv")
proposals_df = pd.read_csv("proposals.csv")
tickets_df =pd.read_csv("service_tickets.csv")
sites_df = pd.read_csv("sites.csv")
def start_sunbun():
    print("\n--- SunBun Assistant ---")
    print("How can we help you today?\n1. Sales Support\n2. Service Support")
    choice = input("Select: ").strip()
    support_type = "Sales Support" if choice == "1" else "Service Support"
    run_authentication(support_type)
def run_prospect_flow(contact_info):
    """
    Section 5.0: Path for unknown users interested in Sales.
    It prepares a temporary user profile and starts the proposal design.
    """
    print("\n[Assistant]: I couldn't find an existing account with those details.")
    print("[Assistant]: No worries! I can help you design a new solar solution from scratch.")
    
    # Create a temporary user dictionary to keep the 'start_new_proposal_flow' happy
    new_prospect = {
        'name': 'New Prospect',
        'email': contact_info if "@" in contact_info else "Not provided",
        'phone': contact_info if "@" not in contact_info else "Not provided",
        'has_proposals': False,
        'customer_id': 'NEW'
    }
    
    # Call your existing Sales function
    start_new_proposal_flow(new_prospect)


def run_authentication(support_type):
    retry_count = 0
    while True:
        print(f"\n--- {support_type} Authentication ---")
        id_choice = input("1. Use Email\n2. Use Phone\nSelect: ").strip()
        id_type = "email" if id_choice == "1" else "phone"
        user_contact = input(f"Enter your {id_type}: ").strip()

        # 1. Check Database First
        cust_match = customers_df[customers_df[id_type].astype(str) == user_contact]
        pros_match = prospects_df[prospects_df[id_type].astype(str) == user_contact]

        # 2. IF NOT IN DB -> Handle Unknown Flow (NO OTP REQUIRED as per requirements)
        if cust_match.empty and pros_match.empty:
            if "Service" in support_type:
                # Section 5.1: First failed lookup
                print("\n[Assistant]: We couldn’t find a system in our records matching this email/phone.")
                print("[Assistant]: If you are an existing SunBun customer, please make sure you’re using the same email or phone number that you used for your monitoring portal.")
                
                if retry_count == 0:
                    print("\nWould you like to try a different email/phone?")
                    print("1. Try again\n2. No, continue anyway")
                    choice = input("Select: ").strip().lower()
                    if "1" in choice or "try" in choice:
                        retry_count += 1
                        continue 
                
                # Section 5.2: Non-SunBun or unregistered system path
                run_external_service_flow(user_contact)
                sys.exit()
            else:
                # Section 7: Sales Support flow – not present in DB
                print("\n[Assistant]: We couldn’t find an existing SunBun system under your details.")
                print("[Assistant]: Let’s collect some information to prepare a customized solar proposal for you.")
                run_prospect_flow(user_contact, id_type)
                sys.exit()

        # 3. IF IN DB -> Perform OTP Verification
        otp_match = email_otp_df[email_otp_df['email'] == user_contact] if id_type == "email" else sms_otp_df[sms_otp_df['phone'] == user_contact]
        correct_otp = str(otp_match.iloc[0]['otp']) if not otp_match.empty else "123456"

        authenticated = False
        for attempt in range(1, 4):
            user_otp = input(f"Enter OTP (Attempt {attempt}/3): ").strip()
            if user_otp == correct_otp:
                print("✅ Identity verified successfully!")
                authenticated = True
                break
            print(f"❌ Incorrect code. {3 - attempt} attempts remaining.")

        if authenticated:
            if not cust_match.empty:
                run_service_flow(cust_match.iloc[0]) if "Service" in support_type else run_sales_flow(cust_match.iloc[0])
            else:
                run_sales_flow(pros_match.iloc[0])
            sys.exit()
        else:
            if "retry" not in input("Retry or Exit? ").lower(): sys.exit()

def run_prospect_flow(identifier, id_type):
    """Section 7: Setup for unknown sales user"""
    new_prospect = {
        'name': 'New Prospect',
        'email': identifier if id_type == "email" else "",
        'phone': identifier if id_type == "phone" else "",
        'has_proposals': False,
        'customer_id': 'NEW'
    }
    start_new_proposal_flow(new_prospect)

def start_new_proposal_flow(user):
    """Section 6.3: Creating new proposals (any user)"""
    print("\n[Assistant]: Let's start by collecting some information for a new proposal.")

    # 1. Customer Context Collection
    if user['customer_id'] == 'NEW':
        name = input("● Please enter your Full Name: ").strip()
    else:
        name = user.get('name', 'Customer')
        print(f"● Name: {name} (Pre-filled)")
    
    # Location context
    postal_code = input("● Enter your Postal Code: ").strip()
    city = input("● Enter your City: ").strip()

    # Contact complement logic
    email = str(user.get('email', ''))
    phone = str(user.get('phone', ''))
    if not email or email == 'nan' or email == "":
        email = input("● Please provide your email address: ").strip()
    if not phone or phone == 'nan' or phone == "":
        phone = input("● Please provide your phone number: ").strip()

    # 2. Segment
    print("\n[Assistant]: Are you a Residential, Commercial, or Industrial customer?")
    print("1. Residential\n2. Commercial\n3. Industrial")
    seg_choice = input("Select: ").strip()
    selected_segment = {"1": "Residential", "2": "Commercial", "3": "Industrial"}.get(seg_choice, "Residential")

    # 3. Demand Information
    try:
        bill_input = input("\n[Assistant]: What is your average monthly electricity bill? ").strip()
        bill = float(bill_input.replace('$', '').replace(',', ''))
    except ValueError:
        bill = 100.0

    increase_input = input("[Assistant]: By what percentage do you expect your consumption to increase (e.g. 10)? ").strip()
    try:
        increase = float(increase_input.replace('%', ''))
    except:
        increase = 0.0

    # 4. Design Preferences
    num_options = input("\n[Assistant]: How many solution options would you like to evaluate right now? (1–3): ")
    num_options = int(num_options) if num_options.isdigit() and 1 <= int(num_options) <= 3 else 1

    print("\n[Assistant]: Do you have any brand preferences? (Inverters: Enphase, SolarEdge, Sungrow, GoodWe | Modules: Jinko, Trina, Waaree)")
    brand_pref = input("Enter brands (or type 'none'): ").strip()

    if brand_pref.lower() == "none":
        print("\n[Assistant]: Would you prefer: [1. Premium] [2. Standard] [3. Budget]? (Select multiple with commas)")
        tier_input = input("Select: ").strip()

    # 5. Backend proposal generation (Sizing logic)
    print("\n[Assistant]: Give us a moment while we design the best options based on your requirements.")
    proposals = []
    for i in range(num_options):
        base_size = round((bill / 25) * (1 + increase / 100), 1)
        prop_id = 9000 + i + random.randint(1, 100)
        proposals.append({
            "proposal_name": f"Option {i+1} - {selected_segment} Plan",
            "id": prop_id,
            "size": base_size + (i * 0.5),
            "savings": round(bill * 0.8, 2),
            "approx_price": f"${int(base_size * 1200)} - ${int(base_size * 1500)}"
        })

    # 7. Show Proposals
    for p in proposals:
        print(f"\nPROPOSAL: {p['proposal_name']} (ID: {p['id']})")
        print(f"● System Size: {p['size']} kW")
        print(f"● Expected Monthly Savings: ${p['savings']}")
        print(f"● Price Band: {p['approx_price']}")
        print("● [Select this option]")

    final_choice = input("\n[Assistant]: Which ID would you like to proceed with? ").strip()
    selected_obj = next((p for p in proposals if str(p['id']) == final_choice), None)

    if selected_obj:
        user['name'] = name # Carry the name forward for confirmation
        confirm_proposal(user, selected_obj)
    else:
        print("[Assistant]: Error selecting proposal. Ending session.")
        sys.exit()

def run_external_service_flow(identifier):
    """Section 5.2: Non-SunBun or unregistered system path"""
    print("\n[Assistant]: It looks like we don’t have your system in our records.")
    print("[Assistant]: We can still help, but we’ll need a few details about your setup.")

    # 1. System Information
    ext_data = {}
    ext_data['size'] = input("\nAssistant: Approximate system size (kWp): ")
    ext_data['brand'] = input("Assistant: Inverter brand/model: ")
    ext_data['year'] = input("Assistant: Year of installation: ")
    ext_data['monitoring'] = input("Assistant: Is online monitoring active? (Yes/No): ")

    # 2. Installer Information
    print("\nAssistant: Who installed your system? (Enter name or 'Don’t remember')")
    ext_data['installer'] = input("Your answer: ")

    # 3. Problem Details
    categories = ["Production Issue", "System Not Working", "Communication Loss", "Battery Failure", "Inverter Failure", "Others"]
    print(f"\nAssistant: Select the category of your issue:\n{categories}")
    ext_data['category'] = input("Category: ")
    ext_data['desc'] = input("Assistant: Please describe the issue in your own words: ")
    ext_data['files'] = input("Assistant: Upload photos (Type 'Uploaded' or 'Skip'): ")

    # 4. Check Agent Availability
    online_agents = agent_avail_df[(agent_avail_df['department'] == 'Service') & (agent_avail_df['is_online'] == True)]
    
    create_ticket = False
    if not online_agents.empty:
        agent = online_agents.iloc[0]['agent_name']
        print(f"\nAssistant: We have a service executive ({agent}) available. Would you like to start a live chat?")
        if "yes" in input("Select (yes/no): ").lower():
            print(f"\n[System]: Handing off to {agent}...")
            print(f"[Context]: External System | Issue: {ext_data['category']}")
            sys.exit()
        else:
            create_ticket = True
    else:
        print("\nAssistant: Our service team is currently offline. I’ll raise a ticket for you.")
        create_ticket = True

    if create_ticket:
        # Sequential ID calculation
        new_id = (tickets_df['ticket_id'].max() + 1) if not tickets_df.empty else 1001
        print(f"\n✅ Assistant: We’ve created a ticket for you: {new_id}.")
        print("[Assistant]: Our team will contact you to discuss next steps. Conversation ended.")
        sys.exit()

def run_service_flow(user):
    print(f"\n[Assistant]: Let me quickly check the status of your solar system in our monitoring platform.")
    site_id = int(user['site_id'])
    
    # 1. Check Site Issues First (Priority 1)
    issue_row = site_issues_df[site_issues_df['site_id'] == site_id]
    
    explanation = ""
    issue_flag = False
    
    if not issue_row.empty and issue_row.iloc[0]['issue_flag']:
        # CASE A: Known Active Issue
        row = issue_row.iloc[0]
        issue_flag = True
        explanation = f"Issue: {row['issue_text']}. Recommended action: {row['recommended_action_text']}"
        print(f"Assistant: We are currently seeing an issue on your system.")
        print(f"Assistant: {explanation}")
        
        # We still need metrics for the log snapshot
        avg_cloudiness = (site_id * 7) % 100
        performance_score = 100 - ((site_id % 5) * 4)
    else:
        # CASE B: No Active Issue (Your Mock Simulation Logic)
        avg_cloudiness = (site_id * 7) % 100  
        performance_score = 100 - ((site_id % 5) * 4) 
        
        site_info = sites_df[sites_df['site_id'] == site_id].iloc[0]
        total_prod = round(site_info['system_size_kw'] * 4.2 * 7 * (performance_score / 100), 1)

        if avg_cloudiness > 60:
            explanation = f"Your system does not show any active faults. However, the last week has been unusually cloudy ({avg_cloudiness}% average) at your location, which is likely why your production has been lower than normal. It should auto-correct as weather improves."
            print(f"Assistant: {explanation}")
        elif performance_score >= 90:
            explanation = f"Your system appears to be performing normally. Last week’s total production was {total_prod} kWh."
            print(f"Assistant: {explanation}")
        else:
            explanation = f"Your system appears to be performing normally. Last week’s total production was {total_prod} kWh. We see a slight underperformance trend, but nothing critical yet. We’ll continue monitoring it."
            print(f"Assistant: {explanation}")

    # Feedback Loop
    print("\nAssistant: Does this answer your question, or would you like to speak to support?")
    print("1. I’m happy with this explanation")
    print("2. I still need help")
    
    res_choice = input("Select (1 or 2): ").strip()

    # --- START AUTO-RESOLUTION PATH (Happy Path) ---
    if res_choice == "1" or "happy" in res_choice.lower():
        print("\nAssistant: Great, we’ll log that your query has been resolved.")
        
        # Log snapshot data as per PDF
        resolved_data = {
            "customer_id": user['customer_id'],
            "site_id": site_id,
            "summary": explanation,
            "issue_flag": issue_flag,
            "metrics_snapshot": {
                "avg_cloudiness": f"{avg_cloudiness}%",
                "performance_score": performance_score
            }
        }
        print(f"[System]: Resolved inquiry logged for Site {site_id}.")

        # NPS Follow-up
        print("\nAssistant: On a scale of 1 to 10, how satisfied are you with the support you received just now?")
        nps = input("Rating (1-10): ")
        
        print("\nAssistant: Anything else you’d like to share about your experience?")
        feedback_text = input("Feedback: ")
        
        print("\nAssistant: Thank you. Your feedback helps us improve. Have a great day!")
        sys.exit() # Conversation ends

    # --- START ESCALATION PATH ---
    elif res_choice == "2" or "help" in res_choice.lower():
        handle_escalation(user, {"cloud": avg_cloudiness, "perf": performance_score})

def handle_escalation(user, monitoring_snapshot):
    print("\n[Assistant]: Sorry to hear that. Let’s understand the issue in a bit more detail.")
    
    # 1. Issue Categories
    categories = [
        "Production Issue", "System Not Working", "Communication Loss", 
        "Battery Failure", "Inverter Failure", "Others"
    ]
    print("\nPlease select the category of your issue:")
    for i, cat in enumerate(categories, 1):
        print(f"{i}. {cat}")
    
    cat_choice = input("Select Category (1-6): ").strip()
    selected_category = categories[int(cat_choice)-1] if cat_choice.isdigit() and 1<=int(cat_choice)<=6 else "Others"

    # 2. Description
    user_desc = input("\n[Assistant]: Please describe the issue in your own words: ").strip()

    # 3. Evidence Collection
    print("\n[Assistant]: If possible, please upload photos or screenshots that show what you’re seeing.")
    print("(e.g., inverter screen, app screenshots, physical damage, etc.)")
    user_attachments = input("Enter file names/links (or type 'none' to skip): ").strip()

    # 4. Check Live Human Availability
    # Check agent_availability.csv for 'Service' department and 'is_online' = True
    available_agents = agent_avail_df[(agent_avail_df['department'] == 'Service') & (agent_avail_df['is_online'] == True)]
    
    chat_handoff = False
    if not available_agents.empty:
        # Case: Service Executive Available
        agent_name = available_agents.iloc[0]['agent_name']
        print(f"\n[Assistant]: We have a service executive ({agent_name}) available right now. Would you like to start a live chat?")
        live_chat = input("Start live chat? (yes/no): ").lower().strip()
        
        if live_chat == "yes":
            print(f"\n[System]: Handing off conversation to {agent_name}...")
            print(f"[System Context]: Site ID {user['site_id']} | Issue: {selected_category}")
            print(f"[Assistant]: {agent_name} has joined the chat. How can they help you further?")
            chat_handoff = True
    else:
        # Case: No Service Executive Available
        print("\n[Assistant]: Our service team is currently offline.")

    # 5. Ticket Creation (Required even if chat is declined or if team is offline)
    if not chat_handoff:
        print("[Assistant]: I’ll create a ticket with all the details you’ve shared so we can follow up.")
        
        ticket_id = 1000 + int(user['customer_id']) # Simulated ID
        
        # Package full ticket data
        ticket_bundle = {
            "ticket_id": ticket_id,
            "customer_id": user['customer_id'],
            "site_id": user['site_id'],
            "category": selected_category,
            "description": user_desc,
            "attachments": user_attachments,
            "monitoring_data_snapshot": monitoring_snapshot
        }
        
        print(f"\n[Assistant]: Your service ticket has been created. Ticket number: {ticket_id}.")
        print("[Assistant]: Our team will reach out to you shortly.")
        print(f"[System Log]: Ticket created with snapshot {monitoring_snapshot}")
    
    print("\n[Assistant]: Thank you for contacting SunBun Solar. Conversation ended.")
    sys.exit()

def run_sales_flow(user):
    """
    Sales Support flow – Sections 6.1 & 6.2: Greeting and Reviewing Proposals
    """
    # 1. Greeting
    print(f"\n[Assistant]: Hi {user['name']}, how can we help with your solar plans today?")
    
    # 2. Check for previous proposals
    if user['has_proposals']:
        print("[Assistant]: We see that we’ve previously shared one or more proposals with you.")
        print("[Assistant]: Would you like to review those, or create new options?")
        print("Buttons: [1. Review old proposals] / [2. Create new proposals]")
        
        choice = input("Select (1 or 2): ").strip()
        
        if choice == "1" or "review" in choice.lower():
            review_old_proposals(user)
        else:
            start_new_proposal_flow(user)
    else:
        print("[Assistant]: I see you're looking for something new. Let's get started.")
        start_new_proposal_flow(user)

def review_old_proposals(user):
    """Section 6.2: Reviewing old proposals from CSV/DB"""
    past_proposals = proposals_df[proposals_df['customer_id'] == user['customer_id']]
    
    if past_proposals.empty:
        print("[Assistant]: I apologize, I couldn't find your past records. Let's create new ones.")
        start_new_proposal_flow(user)
        return

    print("\n[Assistant]: Here are your past proposals:")
    print("-" * 50)
    for index, p in past_proposals.iterrows():
        # Displaying cards as per section 6.2 requirements
        print(f"PROPOSAL CARD")
        print(f"● Name: {p['proposal_name']}")
        print(f"● Approx. Price: {p['approx_price']}")
        print(f"● Est. Yearly Savings: {p.get('yearly_savings', 'TBD')}")
        print(f"● Date Created: {p.get('created_at', '2024-07-01')}")
        print(f"● Status: {p['status']}")
        print(f"● ID: {p['proposal_id']}")
        print(f"● View Link: [www.solyield.com/view/prop_{p['proposal_id']}]")
        print("-" * 50)

    print("\n[Assistant]: Would you like to proceed with any of these proposals, or generate new options?")
    print("1. Proceed with a proposal\n2. Generate new options")
    
    choice = input("Select: ").strip()

    if choice == "1":
        selected_id = input("Enter the Proposal ID you'd like to proceed with: ").strip()
        # Fetch the full dictionary from the dataframe
        match = past_proposals[past_proposals['proposal_id'].astype(str) == selected_id]
        if not match.empty:
            selected_obj = match.iloc[0].to_dict()
            confirm_proposal(user, selected_obj) # Sending the dictionary, NOT just the ID
        else:
            print("ID not found. Returning to menu.")
            review_old_proposals(user)
    else:
        start_new_proposal_flow(user)

def confirm_proposal(user, proposal_id):
    """Section 6.4: Confirmation Handoff"""
    print(f"\n[Assistant]: Excellent choice! I'm marking Proposal ID {proposal_id} for follow-up.")
    print("[Assistant]: A sales executive will reach out to you within 24 hours to finalize the paperwork.")
    print("Thank you for choosing SunBun Solar. Have a great day!")
    sys.exit()

import random

def start_new_proposal_flow(user):
    """Section 6.3: Creating new proposals (any user)"""
    print("\n[Assistant]: Let's collect some information to prepare your customized solar proposal.")

    # 1. Customer Context
    name = input("● Please enter your Full Name: ").strip() if user['customer_id'] == 'NEW' else user['name']
    postal_code = input("● Postal Code: ").strip()
    city = input("● City: ").strip()

    # Contact Complement
    email = user.get('email', '')
    phone = user.get('phone', '')
    if not email or str(email) == 'nan': email = input("● Since we have your phone, please provide your email: ").strip()
    if not phone or str(phone) == 'nan': phone = input("● Since we have your email, please provide your phone: ").strip()

    # 2. Segment
    print("\n[Assistant]: Are you a Residential, Commercial, or Industrial customer?")
    seg = input("Select (Residential/Commercial/Industrial): ").strip()

    # 3. Demand Info
    bill = input("● Average monthly electricity bill: ").strip()
    increase = input("● Expected consumption increase % (e.g. 10): ").strip()

    # 4. Design Preferences
    num = input("● How many options (1-3)? ").strip()
    print("● Brand Preferences? (Inverters: Enphase, SolarEdge, Sungrow, GoodWe | Modules: Jinko, Trina, Waaree)")
    brand = input("Enter brands or 'none': ").strip()
    
    if brand.lower() == "none":
        tier = input("● Prefer Premium, Standard, or Budget? ").strip()

    print("\n[Assistant]: Give us a moment while we design the best options based on your requirements...")
    
    # 6. Backend Generation (Mock)
    mock_proposal = {
        "proposal_name": f"{seg} Solar Plan - {city}",
        "approx_price": "15,000",
        "size": "5 kW",
        "savings": "80%",
        "proposal_id": "NEW_" + str(random.randint(100, 999))
    }

    # 7. Show Results
    print(f"\nPROPOSAL READY: {mock_proposal['proposal_name']}")
    print(f"● Size: {mock_proposal['size']} | Savings: {mock_proposal['savings']}")
    print(f"● Price: {mock_proposal['approx_price']}")
    
    if "yes" in input("\nSelect this option? (yes/no): ").lower():
        user['name'] = name # Update name for confirmation
        confirm_proposal(user, mock_proposal)

def confirm_proposal(user, selected_proposal):
    """Section 6.4: Confirmation and handoff to Inside Sales"""
    # Acknowledge selection
    print(f"\n[Assistant]: Thank you for your interest in the {selected_proposal['proposal_name']} option.")

    # Check Inside Sales availability
    online_sales = agent_avail_df[(agent_avail_df['department'] == 'Sales') & (agent_avail_df['is_online'] == True)]

    if not online_sales.empty:
        # Case: Sales Rep is Online
        print("\n[Assistant]: Would you prefer to speak with our sales representative via call or chat?")
        choice = input("Buttons: [Call] | [Chat]: ").lower().strip()

        if "chat" in choice:
            agent = online_sales.iloc[0]['agent_name']
            print(f"\n[System]: CRM Opportunity created. Opening live chat with {agent}...")
            print(f"[Context]: {user['name']} interested in {selected_proposal['proposal_name']}")
        else:
            print(f"\n[System]: CRM record and Task created: 'Call {user['name']} about {selected_proposal['proposal_name']} within 1 hour.'")
            print("[Assistant]: An expert will call you shortly.")
    else:
        # Case: Sales Rep is Offline
        print("\n[Assistant]: Our sales team is currently unavailable for live conversations, but we’ve logged your interest.")
        print(f"[System]: Opportunity created in CRM for {user['name']}. Follow-up scheduled.")
        print("[Assistant]: You’ll receive a call or email from our team soon.")

    print(f"\n[Assistant]: Thank you for considering SunBun. We’ll be in touch shortly.")
    
    # DO NOT put "import sys" here. Just call the exit.
    sys.exit()

def run_external_service_flow(contact_info):
    """Section 5.2: For unknown Service users (The code you provided earlier)"""
    print("\n[Assistant]: It looks like we don’t have your system in our records. "
          "We can still help, but we’ll need a few details.")
    
    # 1. Collect System Info (KW, Inverter, etc.)
    size = input("Approximate system size (kWp): ")
    brand = input("Inverter brand/model: ")
    year = input("Year of installation: ")
    
    # 2. Check Agents & Create Ticket
    # [Insert the ticket/handoff logic from your previous message here]
    print(f"✅ Ticket created for external system. We will contact you at {contact_info}.")
    sys.exit()

if __name__ == "__main__":
    start_sunbun()