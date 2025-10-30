import streamlit as st
import time
import pandas as pd
from insurance_test import process_claims, process_jira_updates
import requests

st.set_page_config(
    page_title="Insurance Claim Engine",
    layout="wide"
)


if "running" not in st.session_state:
    st.session_state.running = False
if "last_results" not in st.session_state:
    st.session_state.last_results = []
if "logs" not in st.session_state:
    st.session_state.logs = []


st.markdown("""
<h1 style='text-align:center; color:#2E86C1;'>Insurance Claim Processing Engine</h1>
<p style='text-align:center; color:gray;'>
Automatically process email-based insurance claims and Jira updates every 5 minutes.
</p>
""", unsafe_allow_html=True)

st.divider()
col1, col2, col3 = st.columns([1, 1, 3])

with col1:
    if st.button("Start Batch Job", type="primary"):
        st.session_state.running = True
        st.session_state.logs = []
        st.session_state.last_results = []
        st.rerun()

with col2:
    if st.button("Stop Batch Job", type="secondary"):
        st.session_state.running = False
        st.rerun()

with col3:
    st.markdown(
        f"""
        <div style="background-color:#F4F6F6; border-radius:10px; padding:10px; text-align:center;">
        <b>Status:</b> {"<span style='color:green;'>Running</span>" if st.session_state.running else "<span style='color:red;'>Stopped</span>"}
        </div>
        """,
        unsafe_allow_html=True
    )

st.divider()


if st.session_state.running:
    with st.spinner("Running batch job, please wait..."):
        start_time = time.time()
        logs = []
        all_results = []

        for attempt in range(3):
            try:
                results = process_claims()  
                logs.append(f"Claims processed: {len(results)}")
                all_results.extend(results)
                break
            except requests.exceptions.ReadTimeout:
                logs.append(f"Timeout processing claims, retry {attempt+1}/3")
                time.sleep(5)
            except requests.exceptions.ConnectionError:
                logs.append(f"Connection error processing claims, retry {attempt+1}/3")
                time.sleep(5)
            except Exception as e:
                logs.append(f"Unexpected error in claims: {e}")
                results = []
                break

       
        try:
            jira_results = process_jira_updates()  
            all_results.extend(jira_results)
            logs.append("Jira updates processed and customer emails sent")
        except Exception as e:
            logs.append(f"Error processing Jira updates: {e}")

        end_time = time.time()
        st.session_state.last_results = all_results
        st.session_state.logs.extend(logs)

        st.success(f"Batch completed in {end_time - start_time:.2f} seconds.")

        
        st.subheader("Batch Logs")
        for log in logs:
            st.write(f"- {log}")

       
        if all_results:
            st.subheader("Processed Emails and Status")
            df = pd.DataFrame(all_results)
            st.dataframe(df, width="stretch")
            st.caption(f"Processed {len(all_results)} email(s) at {time.strftime('%I:%M:%S %p')}")
        else:
            st.info("No new emails found in this batch.")

      
        st.progress(100, text="Waiting 3 minutes before next run...")
        time.sleep(180)
        st.rerun()


elif st.session_state.last_results:
    st.subheader("Last Batch Results")
    df = pd.DataFrame(st.session_state.last_results)
    st.dataframe(df, width="stretch")
    st.caption(f"Last updated at {time.strftime('%I:%M:%S %p')}")

    if st.session_state.logs:
        st.subheader("Last Batch Logs")
        for log in st.session_state.logs:
            st.write(f"- {log}")

else:
    st.info("No batch has been run yet. Click Start Batch Job to begin processing.")
