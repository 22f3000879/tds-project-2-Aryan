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
       Examples: "POST this JSON to /submit", "What is the sum?", "Get the secret code".
       Do NOT invent a question. Use the text present on the page.
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
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    --- SCRAPED DATA / FILE CONTENT ---
    {file_summary}
    
    INSTRUCTIONS:
    1. If the question asks to "POST this JSON" or provides a JSON sample, extract the value of the "answer" field from that sample.
       (Example: If JSON says "answer": "anything", return "anything").
    2. If the question asks to find a "secret code" or "key", look for "The secret code is [XYZ]" in the Page or Scraped Data.
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
