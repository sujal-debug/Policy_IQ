import os
import json
import re
from datetime import datetime, timedelta
from O365 import Account
from jira import JIRA
import psycopg2
import io
from PyPDF2 import PdfReader
from dotenv import load_dotenv
from langchain_community.agent_toolkits.office365.toolkit import O365Toolkit
from langchain_community.tools.office365.create_draft_message import O365CreateDraftMessage
from langchain_community.tools.office365.events_search import O365SearchEvents
from langchain_community.tools.office365.messages_search import O365SearchEmails
from langchain_community.tools.office365.send_event import O365SendEvent
from langchain_community.tools.office365.send_message import O365SendMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.chains import RetrievalQA
from requests.exceptions import ReadTimeout, RequestException
import time
import logging
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image
import io
import pdfplumber
import base64
import tempfile
import fitz

load_dotenv()

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

JIRA_SERVER = os.getenv("JIRA_SERVER")
JIRA_USER = os.getenv("JIRA_USER")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY")

PG_HOST = os.getenv("PG_HOST")
PG_PORT = os.getenv("PG_PORT")
PG_USER =  os.getenv("PG_USER")
PG_PASSWORD = os.getenv("PG_PASSWORD")
PG_DB = os.getenv("PG_DB")

REDIRECT_URI = "http://localhost:5300"
SCOPES = [
    'https://graph.microsoft.com/Mail.Read',
    'https://graph.microsoft.com/Mail.ReadWrite',
    'https://graph.microsoft.com/Mail.Send',
    'https://graph.microsoft.com/User.Read',
    'offline_access'
]


credentials = (CLIENT_ID, CLIENT_SECRET)
account = Account(credentials)
if not account.is_authenticated:
    account.authenticate(scopes=SCOPES, redirect_uri=REDIRECT_URI)

O365CreateDraftMessage.model_rebuild()
O365SearchEvents.model_rebuild()
O365SearchEmails.model_rebuild()
O365SendEvent.model_rebuild()
O365SendMessage.model_rebuild()
toolkit = O365Toolkit(account=account)
tools = toolkit.get_tools()


llm = ChatGoogleGenerativeAI(
    google_api_key=GOOGLE_API_KEY,
    model="models/gemini-2.5-flash-lite-preview-06-17",
    temperature=0,
    max_output_tokens=2048,
    timeout=60
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

jira_options = {"server": JIRA_SERVER}
jira = JIRA(options=jira_options, basic_auth=(JIRA_USER, JIRA_TOKEN), timeout=30)

def get_connection():
    return psycopg2.connect(
        dbname=PG_DB,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT
    )


embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
vectorstore = Chroma(
    persist_directory="policy_vector_db",
    embedding_function=embedding_model
)
retriever = vectorstore.as_retriever(search_kwargs={"k": 2})


    
def process_jira_updates():
   
    conn = get_connection()
    cursor = conn.cursor()

    
    cursor.execute("""
        SELECT id, email, jira_ticket, status, claim_data
        FROM claims
        WHERE status='submitted'
    """)
    claims = cursor.fetchall()
    results = []
    for claim_id, email, jira_ticket, status, claim_data_json in claims:
        if isinstance(claim_data_json, str):
            claim_data = json.loads(claim_data_json)
        else:
            claim_data = claim_data_json


        issue = jira.issue(jira_ticket)
        issue_status = issue.fields.status.name.lower()

        
        if issue_status in ['approved', 'done', 'processed']:
            subject = "Your Insurance Claim has been Processed"
            body = f"""
            Dear Customer,

             Your insurance claim for policy {claim_data.get('policy_number')} has been processed successfully. 
            The amount approved will reflect in your account within 24-48 hours.

            Thank you for choosing StatusNeo Insurance.
            """
            new_status = 'processed'

        elif issue_status in ['declined', 'rejected']:
            subject = "Your Insurance Claim has been Declined"
            body = f"""
            Dear Customer,

            We regret to inform you that your insurance claim for policy {claim_data.get('policy_number')} has been declined.

            For more details, please contact our support team.

            Thank you,
            StatusNeo Insurance
            """
            new_status = 'declined'
        else:
            continue  

        mailbox = account.mailbox()
        message = mailbox.new_message()
        message.to.add(email)
        message.subject = subject
        message.body = body
        message.send()

        
        cursor.execute(
            "UPDATE claims SET status=%s WHERE id=%s",
            (new_status, claim_id)
        )
        conn.commit()
        results.append({
            "email": email,
            "status": new_status,
            "jira_ticket": jira_ticket
        })

    cursor.close()
    conn.close()
    return results
def parse_json_response(response):
    try:
        cleaned = re.sub(r"```(?:json)?\s*([\s\S]*?)\s*```", r"\1", response.content).strip()
        return json.loads(cleaned)
    except Exception as e:
        print(f" Invalid JSON: {e}")
        return {}
def format_html_email(content: str, company_name: str = "AIG Team") -> str:
    return f"""
    <html>
      <body style="font-family: Calibri, Arial, sans-serif; color: #222; line-height: 1.6; font-size: 15px; background-color:#f9f9f9; padding:20px;">
        <div style="background-color:#fff; border:1px solid #ddd; border-radius:8px; padding:20px; max-width:600px; margin:auto;">
          <p>{content.replace('\n', '<br>')}</p>
          <br>
          <p style="font-size: 13px; color: #555;">
            Regards,<br><b>{company_name}</b>
          </p>
        </div>
      </body>
    </html>
    """





def process_claims():
    mailbox = account.mailbox()
    inbox = mailbox.inbox_folder()
    one_hour_ago = datetime.now() - timedelta(minutes=20)
    query = inbox.new_query().greater_equal('receivedDateTime', one_hour_ago)
    messages = inbox.get_messages(limit=10, query=query, download_attachments=True)



    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    ALTER TABLE claims
    ADD COLUMN IF NOT EXISTS document_data JSONB DEFAULT '{}'::jsonb;
    """)
    

    batch_log = []

    POLICY_REQUIREMENTS = {
        "health": {
            "documents": ["ssn_card", "doctor_bill", "doctor_receipt"],
            "fields": ["patient_name", "policy_number", "date_of_birth", "treatment_date"]
        },
        "vehicle": {
            "documents": ["driver_license", "vehicle_registration", "accident_report"],
            "fields": ["owner_name", "policy_number", "vehicle_number", "accident_date"]
        },
        "life": {
            "documents": ["ssn_card", "death_certificate", "medical_records"],
            "fields": ["beneficiary_name", "policy_number", "date_of_birth", "death_date"]
        }
    }

    def get_required_documents(policy_type: str):
        return POLICY_REQUIREMENTS.get(policy_type, {}).get("documents", [])

    def get_required_fields(policy_type: str):
        return POLICY_REQUIREMENTS.get(policy_type, {}).get("fields", [])

    for msg in messages:
       
        
        email = msg.sender.address if msg.sender else None
        email_body = msg.body or ""
        if not email:
            continue
        
        cursor.execute("SELECT id FROM claims WHERE email=%s", (email,))
        user_exists = cursor.fetchone()
        if not user_exists:
            print(f"Email {email} not found in database. Skipping.")
            mailbox = account.mailbox()
            reply_msg = mailbox.new_message()
            reply_msg.to.add(email)
            reply_msg.subject = "Unable to Process Your Request"
            reply_msg.body = format_html_email("""
            Dear Customer,

            We noticed that your email ID is not registered with us. To access our insurance services and manage your policies, please sign up using your email ID.

            We look forward to serving you and helping you protect what matters most.

            Thank you,
            """)
            reply_msg.body_type = 'HTML'

            reply_msg.send()
            batch_log.append({"email": email, "status": "not_verfied_user"})
            continue
        
        ATTACHMENT_DIR = "Attachments"
        os.makedirs(ATTACHMENT_DIR, exist_ok=True)

        attachments_data = []
        non_pdf_files = []

        if msg.has_attachments:
            for att in msg.attachments:
                filename = att.name

                
                if not filename.lower().endswith('.pdf'):
                    non_pdf_files.append(filename)
                    continue

                try:
                    file_bytes = att.content
                    if isinstance(file_bytes, str):
                        file_bytes = base64.b64decode(file_bytes)

                    
                    name, ext = os.path.splitext(filename)
                    unique_name = f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}{ext}"
                    save_path = os.path.join(ATTACHMENT_DIR, unique_name)

                    
                    with open(save_path, "wb") as f:
                        f.write(file_bytes)

                    attachments_data.append(save_path)
                    print(f" Saved {filename} as {unique_name}")

                except Exception as e:
                    print(f" Failed to save {filename}: {e}")
        else:
            print("No attachments to fetch.")
        
        combined_pdf_text = ""

        for pdf_path in attachments_data:
            try:
                with fitz.open(pdf_path) as doc:
                    pdf_text = ""
                    for page in doc:
                        pdf_text += page.get_text()
                print(f"Extracted text from {os.path.basename(pdf_path)}:\n{pdf_text[:500]}")
                combined_pdf_text += pdf_text + "\n" 
            except Exception as e:
                print(f" Error extracting from {pdf_path}: {e}")

        
                
        if non_pdf_files:
            prompt = f"""
            Write a professional email (no subject, no greeting name) informing the customer:
            The following attachments are not in PDF format: {non_pdf_files}.
            Please resend all attachments in PDF format.
             Strict Rules:
            - DO NOT use asterisks (*), backticks (`), hashtags (#), or bold/italic markers like **text** or *text*.
            - DO NOT use any Markdown syntax.
            - Write in plain professional text only, suitable for Outlook email body.
            - Keep the tone formal, concise, and customer-friendly.
            Company: StatusNeo Insurance.
            """
            response = llm.invoke(prompt)
            reply_msg = msg.reply()
            reply_msg.body = format_html_email(response.content)
            reply_msg.body_type = 'HTML'

            reply_msg.send()
            batch_log.append({"email": email, "status": "rejected_non_pdf", "files": non_pdf_files})
            continue

        
        
        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff",
            retriever=retriever,
            return_source_documents=True
        )
        qa_result = qa_chain.invoke(email_body)
        policy_context = qa_result['result']
        source_docs = qa_result['source_documents']

       
       
        
        prompt_claim = f"""
        You are an insurance claim processor.
        Act like an insurance agent who knows all policy plans.
        and extract the info about the policies.

        Use the following policy reference/context:
        {policy_context}

        Email body:
        {email_body}

        Check for policy type, required feilds and intent like if someone wants to get claim or just want
        to query something.

        1. Detect policy type:
        - Mediclaim / health insurance → "health"
        - Accident / vehicle insurance → "vehicle"
        - Life insurance → "life"
        Return the policy_type in lowercase exactly as above.

        2. Extract all claim fields. Use **exact field names** from the checklist:
        Health fields: ["patient_name", "policy_number", "date_of_birth", "treatment_date"]
        Vehicle fields: ["owner_name", "policy_number", "vehicle_number", "accident_date"]
        Life fields: ["beneficiary_name", "policy_number", "date_of_birth", "death_date"]

        3. Provide a minimal patient/claim summary.

        Always return JSON ONLY in this format:
        {{
            "policy_type": "...",
            ... extracted fields ...,
            "patient_summary": "..."
            "intent": "claim" or "query"
        }}
        """
        
        response_claim = llm.invoke(prompt_claim)

        
        prompt_docs = f"""
            Detect which documents are provided.
            Analyze ONLY the following text extracted from PDF attachments:
            {combined_pdf_text}

            Use exact checklist names:

            Health docs: ["ssn_card", "doctor_bill", "doctor_receipt"]
            Vehicle docs: ["driver_license", "vehicle_registration", "accident_report"]
            Life docs: ["ssn_card", "death_certificate", "medical_records"]

            Return ONLY a JSON in this format:
            {{
            "provided_documents": ["..."]
            }}
            """

        document_response = llm.invoke(prompt_docs)
      
        
        document_data = parse_json_response(document_response)
        
        
        print(" Document Fields & Info:", document_data)
        
        
        claim_data = parse_json_response(response_claim)
        print(" Parsed Claim Data:", claim_data)
        
        

        intent = claim_data.get("intent", "claim").lower()
        print(f" Detected intent: {intent}")

        if intent == "query":

            prompt_agent = f"""
            you are a insurance agent who knows all policy plans.{policy_context}
            start the mail with dear member,
            and tell them whole about the policy plan and dont make it to long just give them short summary about plans.
            that he or she wants to know about.
            be very professional in your font.
            Strict Rules:
            - DO NOT use asterisks (*), backticks (`), hashtags (#), or bold/italic markers like **text** or *text*.
            - DO NOT use any Markdown syntax.
            - Write in plain professional text only, suitable for Outlook email body.
            - Keep the tone formal, concise, and customer-friendly.
            company name: AIG team.

            """
            query_agent = llm.invoke(prompt_agent)
            reply_msg = msg.reply()
            reply_msg.body = format_html_email(query_agent.content)
            reply_msg.body_type = 'HTML'

            reply_msg.subject = "Information Regarding Your Insurance Query"
            reply_msg.send()
            batch_log.append({"email": email, "status": "replied_query"})
            continue 

        cursor.execute(
            "SELECT claim_data, document_data, status FROM claims WHERE email=%s",
            (email,)
        )
        existing_claim = cursor.fetchone()
        print("existing claim fetched from db:")

        if existing_claim:
            existing_claim_json, existing_doc_json, status = existing_claim

            try:
                if isinstance(existing_claim_json, dict):
                    existing_claim_data = existing_claim_json
                elif existing_claim_json:
                    existing_claim_data = json.loads(existing_claim_json)
                else:
                    existing_claim_data = {}
            except Exception:
                existing_claim_data = {}

            try:
                if isinstance(existing_doc_json, dict):
                    existing_document_data = existing_doc_json
                elif existing_doc_json:
                    existing_document_data = json.loads(existing_doc_json)
                else:
                    existing_document_data = {}
            except Exception:
                existing_document_data = {}

        
            for key, value in (claim_data or {}).items():
                if value:
                    existing_claim_data[key] = value

            claim_data_final = existing_claim_data

            existing_docs = set(existing_document_data.get("provided_documents", []))
            new_docs = set((document_data or {}).get("provided_documents", []))
            all_docs = list(existing_docs.union(new_docs))
            document_data_final = {"provided_documents": all_docs}
            print("document if statement is executed")

        else:
            claim_data_final = claim_data or {}
            document_data_final = document_data or {}
            print("document if statement is not executed")

        print(" Claim Fields & Info:")
        print(json.dumps(claim_data_final, indent=2))

        print(" Provided Documents:")
        print(json.dumps(document_data_final, indent=2))

        
        policy_type = claim_data_final.get("policy_type", "unknown")

        policy_type = claim_data_final.get("policy_type")

        if not policy_type or policy_type.lower() not in POLICY_REQUIREMENTS:
            print(f" Unknown or missing policy type for {email}. Sending clarification email.")

            mailbox = account.mailbox()
            reply_msg = mailbox.new_message()
            reply_msg.to.add(email)
            reply_msg.subject = "Unable to Process Your query - Clarification Needed"
            reply_msg.body = """
            <html>
            <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
                <p>Dear Customer,</p>
                <p>
                We could not determine the type of your insurance policy or what kind of claim/query you are making
                 based on your recent email.
                </p>
                <p>
                Please reply with your policy type or provide relevant documents so we can proceed with your claim.
                </p>
                <p>Thank you for choosing <b>AIG</b>.</p>
                <br>
                <p>Best regards,<br>
                <b>AIG Team</b></p>
            </body>
            </html>
            """
            reply_msg.body_type = 'HTML'
            reply_msg.send()

            batch_log.append({"email": email, "status": "unclear_messeage"})
            continue  

        required_fields = get_required_fields(policy_type)
        missing_fields = [f for f in required_fields if not claim_data_final.get(f)]

        required_docs = get_required_documents(policy_type)
        missing_docs = [d for d in required_docs if d not in document_data_final.get("provided_documents", [])]

        

        
        cursor.execute(
            """
            UPDATE claims
            SET claim_data = %s, document_data = %s
            WHERE email = %s
            """,
            (json.dumps(claim_data_final), json.dumps(document_data_final), email)
        )
        conn.commit()

        if missing_docs or missing_fields:
            prompt_missing = f"""
            start the mail with dear member,
            {policy_context} give a short description of the policy that user wants to claim.
            Write a professional email (no subject, no greeting name) informing the customer:
            The following required documents/fields are missing:
            Documents: {missing_docs}
            Fields: {missing_fields}
            Company: AIG team
            Strict Rules:
            - DO NOT use asterisks (*), backticks (`), hashtags (#), or bold/italic markers like **text** or *text*.
            - DO NOT use any Markdown syntax.
            - Write in plain professional text only, suitable for Outlook email body.
            - Keep the tone formal, concise, and customer-friendly.
            """
            response_missing = llm.invoke(prompt_missing)
            reply_msg = msg.reply()
            reply_msg.subject = "Additional Information Required for Your Insurance Claim"
            reply_msg.body = format_html_email(response_missing.content)
            reply_msg.body_type = 'HTML'

            reply_msg.send()

            status = "pending" 
           
            batch_log.append({"email": email, "status": status, "missing_documents": missing_docs, "missing_fields": missing_fields})
            continue

        else:
            prompt_jira = f"""
        
            {policy_context} give a short description of the policy that user wants to claim.
            mailing to get the information about our policy plans and all just tell them about that.
            The customer sent an email and attached PDF documents: #add attachments here
            The extracted claim data is:

            {json.dumps(claim_data_final, indent=2)}
            {json.dumps(document_data_final, indent=2)}

            {combined_pdf_text}
            Provide a comprehensive, human-friendly Jira ticket description including:
            1. Patient/incident history
            2. Summarize each document and give each and every key values means give every possible information
            also add the extract numbers and details mentioned in documents.
            that you have got but in clean and precise way act like insurance claim head.
            3. short AI assessment of claim eligibility and suggested claimable amount
            4. what can be the next steps.
            Make it clear and easy for a human to process.
            Strict Rules:
            - DO NOT use asterisks (*), backticks (`), hashtags (#), or bold/italic markers like **text** or *text*.
            - DO NOT use any Markdown syntax.
            - Write in plain professional text only, suitable for Outlook email body, use only bullets if needed.
            - Keep the tone formal, concise, and customer-friendly.
            - dont add date or time in jira description.
            - all documents and summary is there that is needed to claim just human loop have to verify it write according to it.
            - use from: Insurance Engine.
            company name: AIG team.
            """
            jira_description = llm.invoke(prompt_jira).content

            issue_dict = {
                'project': {'key': JIRA_PROJECT_KEY},
                'summary': f"Insurance Claim - {claim_data_final.get('policy_number')}",
                'description': jira_description,
                'issuetype': {'name': 'Task'}
            }

            def create_issue_with_retries(jira_client, issue_dict, max_retries=3, delay=5):
                for attempt in range(1, max_retries + 1):
                    try:
                        return jira_client.create_issue(fields=issue_dict)
                    except ReadTimeout:
                        logger.warning(f"Jira create_issue timed out (attempt {attempt}/{max_retries}). Retrying in {delay}s...")
                        time.sleep(delay)
                    except RequestException as e:
                        logger.error(f"Jira request error: {e}")
                        time.sleep(delay)
                    except Exception as e:
                        logger.exception(f"Unexpected Jira error: {e}")
                        raise
                raise RuntimeError("Failed to create Jira issue after multiple retries")
            
            issue = create_issue_with_retries(jira, issue_dict)

            prompt_mail = f"""
            Write a professional email (no subject, no greeting name) informing the customer:
            Their claim has been submitted successfully.
            Reference Ticket ID: {issue.key}.
            Company: AIG team.
            Strict Rules:
            - DO NOT use asterisks (*), backticks (`), hashtags (#), or bold/italic markers like **text** or *text*.
            - DO NOT use any Markdown syntax.
            - Write in plain professional text only, suitable for Outlook email body.
            - Keep the tone formal, concise, and customer-friendly.
            """
            response_mail = llm.invoke(prompt_mail)
            reply_msg = msg.reply()
            reply_msg.body = format_html_email(response_mail.content)
            reply_msg.body_type = 'HTML'

            reply_msg.send()
            
            cursor.execute("UPDATE claims SET jira_ticket=%s, status=%s WHERE email=%s",
            (issue.key, "submitted", email))
            
            conn.commit()
        
            batch_log.append({"email": email, "status": "submitted", "jira_ticket": issue.key})

    cursor.close()

    conn.close()
    return batch_log
