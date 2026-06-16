import streamlit as st
from supabase import create_client

sb = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
res = sb.table("matches").select("*").limit(1).execute()
if res.data:
    st.write(list(res.data[0].keys()))
    print("KEYS:", list(res.data[0].keys()), flush=True)
else:
    st.write("No matches found")
    print("No matches found", flush=True)
