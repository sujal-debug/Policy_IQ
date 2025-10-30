# AI-Powered Claims Automation & Query Response System:

An intelligent automation system that streamlines the insurance claim process — from email ingestion to claim tracking and user query handling — using **Python, PostgreSQL, JIRA API, and a RAG-based LLM.


# Project Overview:

This project automates the end-to-end claims workflow for the insurance domain.  
It eliminates manual steps like downloading claim attachments, creating JIRA tickets, and replying to user queries — replacing them with a scalable, AI-driven pipeline.

The system:
- Fetches incoming claim emails automatically.  
- Extracts relevant claim data and attachments.  
- Creates or updates JIRA tickets in real-time.  
- Stores structured claim data in PostgreSQL  
- Uses a Retrieval-Augmented Generation (RAG) setup with an LLM to generate context-aware, policy-driven responses for user queries.

# Key Features:

✅ Automated Claim Processing – Detects and processes claim-related emails automatically.  
✅ User Verification – Validates if the sender is a registered user before processing.  
✅ JIRA Integration – Creates or updates tickets with relevant claim details and attachments.  
✅ RAG-Based Query Resolution – Uses an LLM to provide policy-aware, context-driven answers.  
✅ Batch Job Architecture – Runs periodically and can be scaled to real-time.  
✅ Scalable & Modular Design – Easily extensible for dashboards or analytics.

# Tech Stack:

| Component            | Technology Used                                             |
| -------------------- | ----------------------------------------------------------- |
| Programming Language | Python                                                      |
| Database             | PostgreSQL                                                  |
| Task Type            | Batch Job (scalable to real-time)                           |
| Email Service        | Outlook API (O365)                                          |
| Ticketing System     | JIRA                                                        |
| AI Layer             | Retrieval-Augmented Generation (LLM)                        |

# About

Developed by Sujal Puneyani during internship at Statusneo.
Focused on automating insurance workflows using AI and scalable backend systems.

📧 Contact: sujalpuneyani123@gmail.com
🌐 LinkedIn: https://in.linkedin.com/in/sujal-puneyani-a3a743268
💻 GitHub Repo: https://github.com/sujal-debug/Policy_IQ
