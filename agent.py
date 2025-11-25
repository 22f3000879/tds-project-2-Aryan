import json
import re
import traceback
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, STUDENT_EMAIL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    """
    Analyzes the task to extract the question and URLs.
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
    Solves the question by generating and EXECUTING Python code.
    """
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS / TRANSCRIPTS (The Source of Truth) ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    GENERAL RULES:
    1. **NO NETWORK:** Do NOT use `requests`. Calculate everything locally.
    2. **NO HALLUCINATIONS:** Only use logic/numbers found in the provided text.
    
    SCENARIO LOGIC:
    
    **SCENARIO A: "Anything" Answer**
    - IF JSON sample says `"answer": "anything"`, write: `solution = "anything you want"`
    
    **SCENARIO B: JavaScript Logic (Secret Code)**
    - IF JS logic is present, implement it EXACTLY in Python.
    
    **SCENARIO C: Audio + CSV (The Cutoff Task)**
    - **Step 1:** Read the "AUDIO TRANSCRIPT" rule (e.g. "Sum values > cutoff").
    - **Step 2:** Find the "Cutoff" value.
      - If the page says `innerHTML = await emailNumber()`, you MUST implement `emailNumber` (from `utils.js` content) to get the integer.
    - **Step 3:** Process the CSV.
      - Use `io.StringIO` and `pandas`.
      - Calculate the result.
      - **CRITICAL:** Convert the result to a standard Python integer: `solution = int(result)`.

    **OUTPUT:**
    - Define variable `solution`.
    - Ensure `solution` is a standard `int`, `float`, or `str` (NOT numpy.int64).
    - Return ONLY Python code.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Extract Code
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1)
        else:
            code = content.replace("```python", "").replace("```", "")
            
        print(f"DEBUG: Generated Python Code:\n{code}")
        
        # Shared Scope
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL}
        exec(code, scope, scope)
        
        return scope.get("solution")

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
