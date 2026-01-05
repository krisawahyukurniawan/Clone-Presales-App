# streamlit_app.py

import streamlit as st

# Initialize connection.
conn = st.connection("postgresql", type="sql")

# Perform query.
df = conn.query('SELECT * FROM responsible;', ttl="10m")

# Print results.
for row in df.itertuples():
    st.write(f"{row.id} has a :{row.responsible_name}:")