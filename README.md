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

# Snapshots:


1. Incoming Claim Email

The process begins when a registered user sends a claim request or query via email.
The system, integrated with Microsoft Outlook using the O365 API, automatically fetches new messages from the inbox along with their attachments (such as invoices, claim forms, or policy documents).
![image alt](https://github.com/sujal-debug/Policy_IQ/blob/840bbe55eb547cb1f754571be92697a83af48d51/i_m.png)

2. Claim Data Extraction & Processing
Once a valid email is identified, the system extracts relevant data (like claim ID, policy number, and customer name) from the email body and attachments (PDFs) using PyPDF2 and regex-based parsing.
The claim information is then stored and updated in PostgreSQL, ensuring a structured and trackable record of every claim submission
![image alt](https://github.com/sujal-debug/Policy_IQ/blob/8c27181d3bf544b1a1d5d8b4ca4e386a2ac11714/frontend.png)


3. Automated Acknowledgment & LLM-Based Reply
After validation, the system sends an automated response back to the user.
Using a Retrieval-Augmented Generation (RAG) system, it:
-Fetches relevant policy details from the knowledge base
-Uses an LLM to generate a context-aware reply
-Ensures responses are accurate, personalized, and aligned with internal policies
![image alt](https://github.com/sujal-debug/Policy_IQ/blob/96420c4c1504464b2283e8cbc67910baca8562f9/t_c.png)


4. JIRA Ticket Creation
For every validated claim, a JIRA ticket is automatically raised with the following details:
-Ticket ID: Auto-generated unique identifier
-Reporter: User’s email address
-Description: Extracted claim details and attachments
-Status: Initially set to “Submitted”
![image alt]()
# About

Developed by Sujal Puneyani during internship at Statusneo.
Focused on automating insurance workflows using AI and scalable backend systems.

📧 Contact: sujalpuneyani123@gmail.com
🌐 LinkedIn: https://in.linkedin.com/in/sujal-puneyani-a3a743268
💻 GitHub Repo: https://github.com/sujal-debug/Policy_IQ


