import json
import re
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    prompt = f"""
    You are a scraper parser. Extract strictly valid JSON.
    Keys: "question", "submit_url", "file_url".
    
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
    except:
        return None

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Data Science assistant. 
    
    QUESTION: {question}
    
    --- SCRAPED DATA (Look here first!) ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    INSTRUCTIONS:
    1. If the question implies "POST this JSON", and the JSON contains "answer": "anything", return the string "anything".
    2. If the question asks for a SECRET CODE, look in the SCRAPED DATA.
       - Ignore placeholders like "your secret".
       - Look for explicit statements like "The secret code is 84920".
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
        return "Error"
