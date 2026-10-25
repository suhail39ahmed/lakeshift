import os
import pandas as pd
import snowflake.connector
from snowflake.connector.pandas_tools import write_pandas
from dotenv import load_dotenv

load_dotenv()

def connect():
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        password=os.environ["SNOWFLAKE_PASSWORD"],
        warehouse=os.environ["SNOWFLAKE_WAREHOUSE"],
        database=os.environ["SNOWFLAKE_DATABASE"],
        schema=os.environ["SNOWFLAKE_SCHEMA"],
        enable_server_session_keep_alive_auto_detection=False,
        client_session_keep_alive=True)   # stop the login expiring on long runs

def load_raw(conn):
    # keep_default_na=False keeps '' as '' (Snowflake behaviour), not NULL
    for name in ["raw_customers", "raw_orders", "raw_referrals"]:
        df = pd.read_csv(f"data/{name}.csv", keep_default_na=False, dtype=str)
        df.columns = [c.upper() for c in df.columns]
        if name == "raw_orders":
            df["AMOUNT"] = pd.to_numeric(df["AMOUNT"], errors="coerce")  # blank -> NULL
            df["ORDER_DATE"] = pd.to_datetime(df["ORDER_DATE"]).dt.date
        elif name == "raw_referrals":
            df = df.apply(pd.to_numeric, errors="coerce").astype("Int64")  # blank -> NULL
        else:
            df["SIGNUP_DATE"] = pd.to_datetime(df["SIGNUP_DATE"]).dt.date
        write_pandas(conn, df, name.upper(), auto_create_table=True, overwrite=True)
        if name == "raw_orders":   # Oracle NUMBER is exact decimal: never FLOAT
            conn.cursor().execute("""
                CREATE OR REPLACE TABLE RAW_ORDERS AS
                SELECT ORDER_ID::NUMBER AS ORDER_ID, CUSTOMER_ID::NUMBER AS CUSTOMER_ID, ORDER_DATE,
                AMOUNT::NUMBER(12,2) AS AMOUNT, STATUS
                FROM RAW_ORDERS""")
        if name == "raw_customers":   # ids are numbers in Oracle: sort and compare as numbers
            conn.cursor().execute(
                "CREATE OR REPLACE TABLE RAW_CUSTOMERS AS SELECT * REPLACE (CUSTOMER_ID::NUMBER AS CUSTOMER_ID) FROM RAW_CUSTOMERS")
        print(f"loaded {name}: {len(df)} rows")

if __name__ == "__main__":
    conn = connect()
    print(conn.cursor().execute("SELECT CURRENT_VERSION()").fetchone())
    load_raw(conn)
