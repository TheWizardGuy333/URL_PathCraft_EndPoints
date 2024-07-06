import streamlit as st
import os
from coinbase_commerce.client import Client
import time
from collections import defaultdict
import uuid
import sqlite3
from datetime import datetime, timedelta

# Read secrets from secrets.toml
st.secrets = st.secrets

# Access the Coinbase API key
COINBASE_API_KEY = st.secrets["coinsbase"]["api_key"]
coinbase_client = Client(api_key=COINBASE_API_KEY)

# Database file
DB_FILE = 'database.db'
# Free days for new endpoints
FREE_DAYS = 7

def create_coinbase_charge(amount, currency, user_id):
    try:
        charge = coinbase_client.charge.create(
            name="Add Credits",
            description="Add credits to your account",
            pricing_type="fixed_price",
            local_price={
                "amount": str(amount),
                "currency": currency
            },
            metadata={
                "user_id": user_id
            }
        )
        return charge
    except Exception as e:
        st.error(f"Error creating charge: {str(e)}")
        return None

def generate_payment_link(user_id, amount, currency):
    # Replace 'username' with user_id
    if currency == "Cash App":
        return f"cashapp://pay/${user_id}?amount=${amount}"
    elif currency == "Bitcoin":
        return f"bitcoin:{user_id}?amount={amount}"
    elif currency == "Litecoin":
        return f"litecoin:{user_id}?amount={amount}"
    elif currency == "Ethereum":
        return f"ethereum:{user_id}?amount={amount}"
    elif currency == "DOGE":
        return f"dogecoin:{user_id}?amount={amount}"
    elif currency == "SHIB":
        return f"shibatoken:{user_id}?amount={amount}"
    elif currency == "BTG":
        return f"bitcoingold:{user_id}?amount={amount}"
    elif currency == "BLK":
        return f"blackcoin:{user_id}?amount={amount}"

def create_user():
    ip = st.experimental_get_query_params().get("ip", [""])[0]
    current_time = time.time()
    if create_user.last_creation.get(ip, 0) < current_time - 7 * 24 * 3600:  # 7 days in seconds
        return None
    user_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO users (id, credits) VALUES (?, ?)", (user_id, 0.0))
    conn.commit()
    conn.close()
    create_user.last_creation[ip] = current_time
    return user_id

create_user.last_creation = defaultdict(float)

def get_user_credits(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT credits FROM users WHERE id=?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0.0

def add_user_credits(user_id, amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def create_endpoint(user_id, path, method, response, query_params):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM endpoints WHERE user_id=?", (user_id,))
    endpoint_count = c.fetchone()[0]
    if endpoint_count >= 5:  # Limit to 5 endpoints per user
        conn.close()
        return None
    endpoint_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    expires_at = (datetime.now() + timedelta(days=FREE_DAYS)).isoformat()
    c.execute("""INSERT INTO endpoints (id, user_id, path, method, response, query_params, created_at, expires_at)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", 
              (endpoint_id, user_id, path, method, response, query_params, created_at, expires_at))
    conn.commit()
    conn.close()
    return endpoint_id

def get_user_endpoints(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM endpoints WHERE user_id=?", (user_id,))
    endpoints = c.fetchall()
    conn.close()
    return endpoints

def delete_endpoint(endpoint_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM endpoints WHERE id=?", (endpoint_id,))
    conn.commit()
    conn.close()

def extend_endpoint(endpoint_id, days, is_monthly):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if is_monthly:
        cost = days * 0.1  # Example cost calculation
    else:
        cost = days * 0.05  # Example cost calculation
    c.execute("UPDATE endpoints SET expires_at = datetime(expires_at, '+{} days') WHERE id=?".format(days), (endpoint_id,))
    conn.commit()
    conn.close()
    return cost

def main():
    st.title("URL Endpoint Service")
    st.markdown("""
    ## Welcome to the URL Endpoint Service!
    This service allows you to create and manage custom URL endpoints.
    
    ### How it works:
    1. Create an endpoint by specifying a path, method, and response.
    2. Each endpoint is free for the first 7 days.
    3. After the free period, you can extend your endpoints using credits.
    4. You can create up to 5 endpoints per account.
    
    ### Getting Started:
    - If you're new, an account will be created for you automatically.
    - Your User ID is displayed in the sidebar - keep this for reference!
    """)

    # User management
    if 'user_id' not in st.session_state:
        st.session_state.user_id = create_user()
    user_id = st.session_state.user_id
    st.sidebar.write(f"Your User ID: {user_id}")

    # Display user credits
    credits = get_user_credits(user_id)
    st.sidebar.write(f"Your Credits: ${credits:.2f}")

    # Create new endpoint
    st.header("Create New Endpoint")
    path = st.text_input("Endpoint Path (e.g., /api/data)")
    method = st.selectbox("HTTP Method", ["GET", "POST", "PUT", "DELETE"])
    response = st.text_area("Response (plain text)")
    query_params = st.text_input("Query Parameters (comma-separated, e.g., id,name,value)")

    if st.button("Create Endpoint", key="create_endpoint"):
        endpoint_id = create_endpoint(user_id, path, method, response, query_params)
        if endpoint_id:
            st.success(f"Endpoint created successfully! ID: {endpoint_id}")
            st.info("Your new endpoint is free for the next 7 days. After that, you'll need credits to extend it.")
        else:
            st.error("You've reached the maximum number of endpoints (5). Please delete an existing endpoint to create a new one.")

    # List and manage endpoints
    st.header("Your Endpoints")
    endpoints = get_user_endpoints(user_id)
    if not endpoints:
        st.info("You haven't created any endpoints yet. Use the form above to create your first endpoint!")
    else:
        for endpoint in endpoints:
            with st.expander(f"{endpoint[3]} {endpoint[2]} (Expires: {endpoint[7]})"):
                st.write(f"ID: {endpoint[0]}")
                st.write(f"Query Parameters: {endpoint[5]}")
                st.text(f"Response: {endpoint[4]}")
                if st.button("Delete", key=f"delete_{endpoint[0]}"):
                    delete_endpoint(endpoint[0])
                    st.success("Endpoint deleted successfully!")
                    st.experimental_rerun()

if __name__ == "__main__":
    main()
    
