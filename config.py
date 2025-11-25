import os

# --- YOUR DETAILS ---
# REPLACE THESE WITH YOUR ACTUAL DETAILS BEFORE DEPLOYING
STUDENT_EMAIL = "22f3000879@ds.study.iitm.ac.in" 
STUDENT_SECRET = "22f3000879"

# --- OPENAI SETTINGS ---
# Ensure you add this Key in Render's "Environment Variables" section
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
OPENAI_MODEL = "gpt-4o-mini"
