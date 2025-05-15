import streamlit as st
import pandas as pd
from google.cloud import bigquery
from docx import Document
from datetime import datetime
import openai
import os

# Setup
openai.api_key = st.secrets["REDACTED"]
project_id = "radar-377104"
with open("gcp_key.json", "w") as f:
    f.write(st.secrets["GOOGLE_APPLICATION_CREDENTIALS"])
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "gcp_key.json"

# === Define system message globally so it's always available ===
system_message = """RADaR Analysis is a marketing consultant GPT that analyzes monthly marketing data provided by users in CSV format and generates structured insights based on a specific format. It follows a data-driven approach, identifying trends, key performance indicators (KPIs), and actionable recommendations.

### Data Structure:
The CSV file contains the following columns: Campaign Group, Channel, Impressions, Clicks, CTR, Sessions, Revenue, and Month-over-Month (MoM) and Year-over-Year (YoY) comparisons for these KPIs. 
- **Media spend dollar amounts will not be provided and should not be included in the output.**
- **MoM and YoY media spend changes are included and should be analyzed.**
- **A change in media spend is likely to impact impressions and clicks, which should be taken into account.**

### Insight Format:
1. **Executive Summary (Overall):**
   - A paragraph summarizing the good and bad performance for all campaign groups and channels.
   - Uses the 'Total' row in the CSV for overall performance analysis.
   - Considers marketing strategy, channel mix, and real-world marketing knowledge in the assessment.

2. **Campaign Group Insights (One section per campaign group):**
   - Named dynamically based on the campaign group name.
   - Includes a high-level executive summary written as a paragraph, focusing on the '[Campaign Group] Subtotal' row.
   - If the campaign group is 'Membership,' focuses on YoY performance.
   - For other campaign groups, focuses on MoM performance.
   - Mentions only performance changes above 5%, highlighting specific channels driving the changes.
   - Recognizes the relationship between media spend shifts and impressions/clicks.

3. **Channel Breakdown (Under each Campaign Group Section):**
   - Lists each individual channel within the campaign group.
   - Provides three bullet points per channel:
     - Two pros (what went well).
     - Two cons (what could be improved).
   - Considers marketing best practices, channel mix efficiency, and strategic opportunities.

4. **Additional Campaign Group Sections:**
   - Follows the same structure as above for each additional campaign group in the file.

### Additional Notes:
- Kimbell Analysis strictly follows this hierarchy and structure.
- The Executive Summary and each Campaign Group's Executive Summary must be written as paragraphs, not bullet points.
- It does not assume missing data but will ask the user for clarification if needed.
- The tone is professional, concise, and strategic, avoiding unnecessary elaboration.
- Insights are based on quantitative evidence, with a focus on metrics-based conclusions.
- Uses real-world marketing expertise to assess strategy, channel performance, and market trends beyond just numerical analysis.
- Can also provide general marketing strategies, industry benchmarks, and best practices upon request.
"""

st.title("📊 Monthly Marketing Analysis")

# === Session State Setup ===
if "analysis_output" not in st.session_state:
    st.session_state.analysis_output = None
if "followup_count" not in st.session_state:
    st.session_state.followup_count = 0
if "conversation_history" not in st.session_state:
    st.session_state.conversation_history = []

# === Month Selector ===
month_options = ["2025-01","2025-02","2025-03", "2025-04"]  # Extend if needed
selected_month = st.selectbox("Select Month for Analysis", options=month_options)

# === Run Analysis Button ===
if st.session_state.analysis_output is None:
    if st.button("Run Analysis"):
        with st.spinner(f"Running analysis for {selected_month}..."):

            # --- BigQuery ---
            query = f"""
            SELECT * 
            FROM `radar-377104.Schaefer_Kimbell.ai_insights_monthly_table`
            WHERE Month_String = '{selected_month}'
            """
            client = bigquery.Client(project=project_id)
            df = client.query(query).to_dataframe()
            csv_data = df.to_csv(index=False)

            # --- GPT Analysis ---
            prompt = f"""Here is the CSV data for {selected_month}:\n\n{csv_data}\n\nPlease generate the structured insights as instructed."""

            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )

            result = response.choices[0].message.content
            st.session_state.analysis_output = result
            st.session_state.conversation_history = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": result}
            ]

# === Show Initial Output ===
if st.session_state.analysis_output:
    st.subheader(f"🧠 GPT Analysis for {selected_month}")
    st.markdown(st.session_state.analysis_output)

    # === Follow-up questions (up to 3) ===
    if st.session_state.followup_count < 3:
        followup = st.text_input("Ask a follow-up question about the data", key=f"followup_{st.session_state.followup_count}")

        if followup:
            with st.spinner("Thinking..."):
                st.session_state.conversation_history.append({"role": "user", "content": followup})

                response = openai.chat.completions.create(
                    model="gpt-4",
                    messages=st.session_state.conversation_history,
                    temperature=0.3,
                    max_tokens=600
                )

                reply = response.choices[0].message.content
                st.session_state.conversation_history.append({"role": "assistant", "content": reply})

                st.session_state.followup_count += 1
                st.markdown(f"#### 💬 GPT Reply #{st.session_state.followup_count}")
                st.markdown(reply)
# === Final action buttons ===
if st.button("🔁 Reset Analysis"):
    st.session_state.analysis_output = None
    st.session_state.followup_count = 0
    st.session_state.conversation_history = []
    st.rerun()

from io import BytesIO
from docx import Document
from datetime import datetime

if st.button("📄 Export to .docx"):
    doc = Document()
    doc.add_heading(f"Marketing Analysis – {selected_month}", 0)

    for msg in st.session_state.conversation_history:
        role = msg["role"]
        if role == "user":
            doc.add_paragraph(f"User:\n{msg['content']}")
        elif role == "assistant":
            doc.add_paragraph(f"Kimbell Analysis:\n{msg['content']}")

    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)

    filename = f"Analysis_{selected_month}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
    st.download_button(
        label="📄 Download .docx File",
        data=buffer,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )