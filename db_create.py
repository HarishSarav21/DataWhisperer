import pandas as pd
import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')
# --- Load CSVs ---
ad_sales_path = "Anarix_AI\DATASET\Product-Level Ad Sales and Metrics (mapped).csv"
total_sales_path = "Anarix_AI\DATASET\Product-Level Total Sales and Metrics (mapped).csv"
eligibility_path = "Anarix_AI\DATASET\Product-Level Eligibility Table (mapped).csv"

ad_sales_df = pd.read_csv(ad_sales_path)
total_sales_df = pd.read_csv(total_sales_path)
eligibility_df = pd.read_csv(eligibility_path)

# --- Create SQLite DB ---
conn = sqlite3.connect("ecommerce.db")

# --- Write DataFrames to SQL Tables ---
ad_sales_df.to_sql("ad_sales", conn, if_exists="replace", index=False)
total_sales_df.to_sql("total_sales", conn, if_exists="replace", index=False)
eligibility_df.to_sql("eligibility", conn, if_exists="replace", index=False)

print("✅ All tables loaded into ecommerce.db")

# --- Helper to run SQL ---
def run_query(query):
    with sqlite3.connect("ecommerce.db") as conn:
        return pd.read_sql_query(query, conn)

# --- Example query ---
if __name__ == "__main__":
    sample = run_query("SELECT * FROM ad_sales LIMIT 5;")
    print("🧪 Sample Result from ad_sales:\n", sample)


    cursor = conn.cursor()

    # Query to get all table names
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()

    # Print the results
    print("📋 Tables in ecommerce.db:")
    for table in tables:
        print("-", table[0])

    conn.close()
