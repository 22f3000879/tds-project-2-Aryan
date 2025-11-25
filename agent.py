import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    """
    Analyzes the task.
    """
    prompt = f"""
    You are a scraper parser. Extract strictly valid JSON from this content.
    
    Keys: 
    - "question": Extract the EXACT instruction text from the page. 
    - "submit_url": The URL to POST the answer to.
    - "file_url": Look for "Download" links or "Scrape" links (hrefs). If none, null.

    OUTPUT RAW JSON ONLY.
    
    CONTENT:
    {decoded_html[:15000]}
    """
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "")
        return json.loads(content.strip())
    except Exception as e:
        print(f"Parse Error: {e}")
        return None

def solve_question(question: str, file_summary: str, page_content: str = ""):
    """
    Solves the question.
    """
    prompt = f"""
    You are a Data Science assistant. 
    
    QUESTION: {question}
    
    --- SCRAPED DATA / FILE CONTENT (THE ANSWER IS HERE) ---
    {file_summary}
    
    --- PAGE CONTENT (Instructions & Samples) ---
    {page_content[:10000]}
    
    CRITICAL INSTRUCTIONS:
    1. **PRIORITIZE THE SCRAPED DATA.** The Page Content often contains a *Sample JSON* with placeholders like "your secret" or "12345". **IGNORE THESE PLACEHOLDERS.**
    2. Look inside the **SCRAPED DATA** section above for the real answer.
       - Look for: "The secret code is [CODE]"
       - Look for: "Key: [CODE]"
    3. If the question asks to "POST this JSON" (Step 1), then you can use the sample data.
    4. Return strictly JSON: {{ "answer": "YOUR_ANSWER" }}
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1].replace("json", "")
        return json.loads(content.strip())["answer"]
    except Exception as e:
        print(f"Solve Error: {e}")
        return None
