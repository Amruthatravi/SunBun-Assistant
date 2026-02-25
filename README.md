# SunBun Solar Assistant - AI Logic Engine

## 1. Project Description
This project is a Python-based conversational assistant for SunBun Solar. It handles complex customer journeys across Sales and Service departments. 

### Architecture & Design Choices
- **Hybrid Logic:** Uses deterministic calculations for solar sizing ($$Price = Size \times Rate$$) and agentic routing for user intent.
- **Identity Handling:** Features a custom authentication layer that skips OTP for unknown users to reduce friction in the sales funnel.
- **Scalability:** Built using a modular function-based design, making it ready for future LLM API integration.

## 2. Video Walkthrough
[Click here to watch the demonstration video](INSERT_YOUR_YOUTUBE_OR_DRIVE_LINK_HERE)

## 3. Screenshots
### Authentication Flow
![Auth Screen](INSERT_LINK_TO_SCREENSHOT_1)
### Proposal Generation
![Proposal Screen](INSERT_LINK_TO_SCREENSHOT_2)
### Service Ticket Creation
![Ticket Screen](INSERT_LINK_TO_SCREENSHOT_3)

## 4. How to Run
1. Clone the repository.
2. Ensure `pandas` is installed: `pip install pandas`
3. Run `python sample1.py`.