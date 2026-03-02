
import streamlit as st
from crud import get_columns, insert_record

IGNORE_COLUMNS = ['id', 'status', 'created_by', 'approved_by', 'approved_at', 'created_at']

def generate_form(table_name, username):
    columns = get_columns(table_name)
    form_data = {}

    with st.form(table_name):
        for col in columns:
            if col in IGNORE_COLUMNS:
                continue

            if "date" in col:
                form_data[col] = st.date_input(col)
            elif "amount" in col or "cost" in col or "percent" in col:
                form_data[col] = st.number_input(col, step=1.0)
            elif "year" in col:
                form_data[col] = st.number_input(col, step=1)
            else:
                form_data[col] = st.text_input(col)

        submitted = st.form_submit_button("Submit")

        if submitted:
            form_data["created_by"] = username
            insert_record(table_name, form_data)
            st.success("Record Submitted Successfully!")
