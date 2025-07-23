import streamlit as st
import sqlite3
import pandas as pd
import requests
import json

# Load CSVs and initialize DB
ad_sales_path = "DATASET\\Product-Level Ad Sales and Metrics (mapped).csv"
total_sales_path = "DATASET\\Product-Level Total Sales and Metrics (mapped).csv"
eligibility_path = "DATASET\\Product-Level Eligibility Table (mapped).csv"

ad_sales_df = pd.read_csv(ad_sales_path)
total_sales_df = pd.read_csv(total_sales_path)
eligibility_df = pd.read_csv(eligibility_path)

conn = sqlite3.connect("ecommerce.db")
ad_sales_df.to_sql("ad_sales", conn, if_exists="replace", index=False)
total_sales_df.to_sql("total_sales", conn, if_exists="replace", index=False)
eligibility_df.to_sql("eligibility", conn, if_exists="replace", index=False)
conn.close()

# --- CONFIG ---
DB_PATH = "ecommerce.db"
OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "mistral"

# --- SQL GENERATION FUNCTION (with streaming) ---
def generate_sql_from_question(question):
    prompt = f"""
You are an expert SQL developer. Your ONLY job is to translate natural language questions into syntactically correct **SQLite** queries.

🔧 Rules:
- 🔥 Output **only** the SQL query. No extra comments, explanations, or formatting.
- ✅ Use only **SQLite-compatible** syntax.
- ❌ DO NOT use unsupported functions like `EXTRACT`, `DATE_TRUNC`, `TO_CHAR`, etc.
- 📅 For date manipulations, use **`strftime()`**:
  - `%Y-%m` for month
  - `%Y-%m-%d` for day
  - Always apply it with **table alias**, e.g. `strftime('%Y-%m', ad_sales.date)`
- 🔄 Avoid ambiguity in JOINs — always qualify column names with table alias.
- 🧮 Use **GROUP BY** if aggregation like `SUM`, `AVG`, `COUNT` is used.
- 👀 Use `JOIN` only if columns like `item_id` or `date` exist in both tables.
- 💡 When combining metrics (e.g., ad_sales + total_sales), make sure both fields exist in context.
- 🧩 Always use variables along with table names so that it is more specific when joining 2 different tables.

📦 SQLite Database Schema:
- ad_sales(date, item_id, ad_sales, impressions, ad_spend, clicks, units_sold)
- total_sales(date, item_id, total_sales, total_units_ordered)
- eligibility(eligibility_datetime_utc, item_id, eligibility, message)

📘 Examples:
Q: What is my total sales?
SQL: SELECT SUM(total_sales.total_sales) AS total_sales FROM total_sales;

Q: Calculate the RoAS (Return on Ad Spend).
SQL: SELECT SUM(ad_sales.ad_sales) * 1.0 / SUM(ad_sales.ad_spend) AS roas FROM ad_sales;

Q: Which product had the highest CPC?
SQL: SELECT ad_sales.item_id, ad_sales.ad_spend * 1.0 / ad_sales.clicks AS cpc FROM ad_sales WHERE ad_sales.clicks > 0 ORDER BY cpc DESC LIMIT 1;

Q: What is the sales of each month?
SQL: SELECT strftime('%Y-%m', ad_sales.date) AS month, SUM(ad_sales.ad_sales + total_sales.total_sales) AS total_monthly_sales FROM ad_sales JOIN total_sales ON ad_sales.item_id = total_sales.item_id AND strftime('%Y-%m', ad_sales.date) = strftime('%Y-%m', total_sales.date) GROUP BY month;

Q: What is the sales of each date?
SQL: SELECT ad_sales.date, SUM(ad_sales.ad_sales + total_sales.total_sales) AS total_daily_sales FROM ad_sales JOIN total_sales ON ad_sales.item_id = total_sales.item_id AND ad_sales.date = total_sales.date GROUP BY ad_sales.date;

Q: Which item has the highest sales?
SQL: SELECT ad_sales.item_id, SUM(ad_sales.ad_sales + total_sales.total_sales) AS total_item_sales FROM ad_sales JOIN total_sales ON ad_sales.item_id = total_sales.item_id GROUP BY ad_sales.item_id ORDER BY total_item_sales DESC LIMIT 1;

Q: Total clicks and units sold per item?
SQL: SELECT ad_sales.item_id, SUM(ad_sales.clicks) AS total_clicks, SUM(ad_sales.units_sold) AS total_units_sold FROM ad_sales GROUP BY ad_sales.item_id;

Q: Items with no eligibility message?
SQL: SELECT eligibility.item_id FROM eligibility WHERE eligibility.message IS NULL;

Q: Items eligible in last 30 days?
SQL: SELECT eligibility.item_id FROM eligibility WHERE eligibility.eligibility_datetime_utc >= date('now', '-30 days');

Q: Sales growth month-over-month?
SQL: SELECT strftime('%Y-%m', ad_sales.date) AS month, SUM(ad_sales.ad_sales + total_sales.total_sales) AS total_sales FROM ad_sales JOIN total_sales ON ad_sales.item_id = total_sales.item_id AND ad_sales.date = total_sales.date GROUP BY month ORDER BY month;

Q: CTR (Click-through Rate) per item?
SQL: SELECT ad_sales.item_id, SUM(ad_sales.clicks) * 1.0 / SUM(ad_sales.impressions) AS ctr FROM ad_sales WHERE ad_sales.impressions > 0 GROUP BY ad_sales.item_id;

Q: Conversion Rate (units_sold to clicks)?
SQL: SELECT ad_sales.item_id, SUM(ad_sales.units_sold) * 1.0 / SUM(ad_sales.clicks) AS conversion_rate FROM ad_sales WHERE ad_sales.clicks > 0 GROUP BY ad_sales.item_id;

Q: Eligible items with total sales?
SQL: SELECT eligibility.item_id, SUM(total_sales.total_sales) AS total_sales FROM eligibility JOIN total_sales ON eligibility.item_id = total_sales.item_id WHERE eligibility.eligibility = 'TRUE' GROUP BY eligibility.item_id;

Q: Sales of items marked ineligible?
SQL: SELECT eligibility.item_id, SUM(total_sales.total_sales) AS total_sales FROM eligibility JOIN total_sales ON eligibility.item_id = total_sales.item_id WHERE eligibility.eligibility = 'FALSE' GROUP BY eligibility.item_id;

Q: Top 5 products by ad_spend?
SQL: SELECT ad_sales.item_id, SUM(ad_sales.ad_spend) AS total_spend FROM ad_sales GROUP BY ad_sales.item_id ORDER BY total_spend DESC LIMIT 5;

Q: Most recent eligibility message per item?
SQL: SELECT eligibility.item_id, MAX(eligibility.eligibility_datetime_utc) AS latest_check FROM eligibility GROUP BY eligibility.item_id;

Now convert this question into SQL:
Q: {question}
SQL:
"""
    sql_result = ""
    with requests.post(OLLAMA_URL, json={"model": MODEL_NAME, "prompt": prompt, "stream": True}, stream=True) as response:
        for line in response.iter_lines():
            if line:
                try:
                    if line.startswith(b"data:"):
                        line = line[len("data: "):]
                    json_chunk = json.loads(line.decode("utf-8"))
                    sql_result += json_chunk.get("response", "")
                except Exception as e:
                    return f"Error parsing response: {str(e)}"
    return sql_result

# --- SQL EXECUTION FUNCTION ---
def run_sql_query(sql):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            df = pd.read_sql_query(sql, conn)
        return df
    except Exception as e:
        return f"SQL Error: {str(e)}"

# --- SCHEMA VIEWER FUNCTION ---
def get_table_schema():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()
        schema = {}
        for table_name, in tables:
            cols = cursor.execute(f"PRAGMA table_info({table_name});").fetchall()
            schema[table_name] = [(str(col[1]), str(col[2])) for col in cols]
        return schema

# --- STREAMLIT UI ---
st.set_page_config(page_title="🔍 Data Whisperer", layout="centered")

st.markdown("""
    <style>
    .fixed-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #0e1117;
        padding: 10px 20px;
        z-index: 100;
    }
    .chat-scroll {
        max-height: 80vh;
        overflow-y: auto;
    }
    </style>
""", unsafe_allow_html=True)
header = st.container()

header.title(" 🔍 Data Whisperer: AI Powered")
header.write("""<div class='fixed-header'/>""", unsafe_allow_html=True)

### Custom CSS for the sticky header
st.markdown(
    """
<style>
    div[data-testid="stVerticalBlock"] div:has(div.fixed-header) {
        position: sticky;
        top: 2.875rem;
        background-color: #0e1117;
        z-index: 999;
        

    }
    .fixed-header {
        border-bottom: 1px solid #0e1117;
    }
    h1{
        line-height: 0.7;
    }
</style>
    """,
    unsafe_allow_html=True
)
# Custom CSS to widen content area
st.markdown("""
    <style>
    /* Override Streamlit's default max-width */
    .block-container {
        max-width: 55rem !important;
        
    }
    </style>
""", unsafe_allow_html=True)


#st.markdown("# 🔍 Data Whisperer: AI Powered", unsafe_allow_html=True)

with st.sidebar:
    st.markdown("# 🗃️ Database Schema")
    schema = get_table_schema()
    for table, columns in schema.items():
        with st.expander(f"📁 {table}"):
            schema_lines = [
                f"{'└──' if i == len(columns)-1 else '├──'} <b>{col}</b> : <span style='color:gray;font-size:0.9em'>{typ}</span>"
                for i, (col, typ) in enumerate(columns)
            ]
            st.markdown("<br>".join(schema_lines), unsafe_allow_html=True)



if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

with st.container():
    #st.markdown("## Chat History")
    container = st.container()
    with container:
        for idx, (q, sql, res) in enumerate(st.session_state.chat_history):
            st.markdown(f"#### **Q{idx+1}: {q}**")
            st.code(sql, language="sql")
            if isinstance(res, pd.DataFrame):
                st.dataframe(res)
                if res.shape[1] == 2 and pd.api.types.is_numeric_dtype(res.iloc[:, 1]):
                    st.bar_chart(res.set_index(res.columns[0]))
                elif res.shape[1] == 2 and pd.api.types.is_numeric_dtype(res.iloc[:, 0]):
                    st.line_chart(res.set_index(res.columns[0]))
                elif res.shape[1] == 2 and pd.api.types.is_object_dtype(res.iloc[:, 0]):
                    st.pyplot(res.set_index(res.columns[0]).plot.pie(y=res.columns[1], autopct="%.1f%%").figure)
                csv = res.to_csv(index=False).encode("utf-8")
                st.download_button(f"💾Export Q{idx+1} as CSV", csv, f"query_result_{idx+1}.csv", "text/csv")
            else:
                st.error(res)

with st.container():
    st.markdown('<div class="fixed-footer">', unsafe_allow_html=True)
    question = st.text_input("Ask a question about your e-commerce data:", placeholder="e.g. What is my total sales?", key="chat_input")
    if question and question != st.session_state.get("last_question"):
        with st.spinner("Mistral is thinking..."):
            sql = generate_sql_from_question(question)
            result = run_sql_query(sql)
            st.session_state.chat_history.append((question, sql, result))
            st.session_state.last_question = question
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)
