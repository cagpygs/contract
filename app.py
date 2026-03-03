import psycopg2
import os
import streamlit as st
import datetime
import plotly.express as px
from auth import login
from crud import *

st.set_page_config(layout="wide")

# ================= SESSION =================
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

# ================= LOGIN =================
if not st.session_state.logged_in:

    st.title("Login")

    u = st.text_input("Username")
    p = st.text_input("Password", type="password")

    if st.button("Login"):
        user = login(u, p)
        if user:
            st.session_state.logged_in = True
            st.session_state.user_id = user["id"]
            st.session_state.username = user["username"]
            st.session_state.role = user["role"]
            st.rerun()
        else:
            st.error("Invalid login")

    st.stop()

# ================= AFTER LOGIN =================
if "master_id" not in st.session_state:
    st.session_state.master_id = None

user_id = st.session_state.user_id
is_admin = st.session_state.role == "admin"

# ================= TOP BAR =================
col1, col2, col3 = st.columns([7, 2, 1])

with col1:
    st.markdown("## 🏗️ Canal Management Dashboard")
    st.caption("Application Submission System")

with col2:
    st.markdown(f"👤 **{st.session_state.username}**")

with col3:
    if st.button("Logout"):
        st.session_state.clear()
        st.rerun()
