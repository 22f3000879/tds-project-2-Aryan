import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    """
    Analyzes the task. Now explicitly looks for scraping links.
    """
    prompt = f"""
    You are a scraper parser. Extract strictly valid JSON from this content.
    
    Keys: 
    - "question": The task (e.g. "Get the secret code").
    - "submit_url": The POST URL.
    - "file_url": Look for ANY data link. This includes:
         1. "Download" links (PDF/CSV)
         2. "Scrape" links (e.g. "Scrape data from this page")
         3. "Source" links
         If multiple exist, pick the one most likely to contain the answer data. If none, null.

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
    
    --- PAGE CONTENT (The answer might be here) ---
    {page_content[:10000]}
    
    --- SCRAPED DATA / FILE CONTENT (The answer is LIKELY here) ---
    {file_summary}
    
    INSTRUCTIONS:
    1. The answer is usually in the SCRAPED DATA section.
    2. Look for patterns like "The secret code is [XYZ]", "Key: [XYZ]".
    3. Return strictly JSON: {{ "answer": "YOUR_ANSWER" }}
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
