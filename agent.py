import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    prompt = f"""
    You are a scraper parser. Extract strictly valid JSON from this content.
    Keys: "question" (the task), "submit_url", "file_url" (or null).
    OUTPUT RAW JSON ONLY. NO MARKDOWN.
    
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
        # Clean markdown if present
        if "```" in content:
            content = content.split("```")[1].replace("json", "")
        return json.loads(content.strip())
    except Exception as e:
        print(f"Parse Error: {e}")
        return None

def solve_question(question: str, file_summary: str, page_content: str = ""):
    """
    Solves the question using the page content and file data.
    """
    prompt = f"""
    You are a Data Science assistant. 
    
    QUESTION: {question}
    
    --- PAGE CONTENT (The answer is hidden here) ---
    {page_content[:15000]}
    
    --- FILE CONTENT ---
    {file_summary}
    
    INSTRUCTIONS:
    1. Look for patterns like "The secret code is [XYZ]", "Key: [XYZ]", or simple codes.
    2. Ignore URL parameters like "?email=".
    3. Return strictly JSON: {{ "answer": "YOUR_ANSWER" }}
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        # Clean markdown if present
        if "```" in content:
            content = content.split("```")[1].replace("json", "")
        return json.loads(content.strip())["answer"]
    except Exception as e:
        print(f"Solve Error: {e}")
        return None
