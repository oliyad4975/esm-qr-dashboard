import streamlit as st
import pandas as pd
import os
from datetime import datetime

# Set page configuration for professional presentation
st.set_page_config(
    page_title="ESM CAPA Dashboard",
    page_icon="📊",
    layout="wide"
)

# Application Header
st.title("📊 ESM CAPA Management Dashboard")
st.markdown("---")

# Helper function to ensure output directories exist
def ensure_directories():
    if not os.path.exists("output/esm_labels"):
        os.makedirs("output/esm_labels")

# Dashboard Logic
def main():
    ensure_directories()
    
    # Sidebar Navigation
    menu = ["Dashboard Overview", "Submit New CAPA", "Audit Logs"]
    choice = st.sidebar.selectbox("Navigation", menu)

    if choice == "Dashboard Overview":
        st.subheader("System Status")
        # Placeholder for data visualization
        st.info("Metrics and analytics will be loaded here.")
        
    elif choice == "Submit New CAPA":
        st.subheader("New CAPA Submission")
        with st.form("capa_form"):
            col1, col2 = st.columns(2)
            with col1:
                capa_id = st.text_input("CAPA ID")
                category = st.selectbox("Category", ["Hardware", "Software", "Process"])
            with col2:
                date = st.date_input("Date", datetime.now())
                priority = st.select_slider("Priority", options=["Low", "Medium", "High"])
            
            description = st.text_area("Root Cause Description")
            submit = st.form_submit_button("Generate Label")

            if submit:
                if capa_id:
                    st.success(f"CAPA {capa_id} submitted successfully!")
                    # Add logic for file generation here
                else:
                    st.error("CAPA ID is required.")

    elif choice == "Audit Logs":
        st.subheader("System Logs")
        st.write("Displaying recent activity...")

if __name__ == "__main__":
    main()