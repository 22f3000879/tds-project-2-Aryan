import json
import re
import traceback
from openai import OpenAI
from config import OPENAI_API_KEY, OPENAI_MODEL, STUDENT_EMAIL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    prompt = f"""
    You are a scraper parser. Extract strictly valid JSON.
    Keys: "question", "submit_url", "file_url".
    CONTENT: {decoded_html[:15000]}
    """
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0
        )
        content = response.choices[0].message.content.strip()
        if "```" in content: content = content.split("```")[1].replace("json", "")
        return json.loads(content.strip())
    except: return None

def sanitize_code(code: str):
    code = re.sub(r'^import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^import urllib.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    if "demo2_key" in code and "7919" not in code: 
        code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)
    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS / TRANSCRIPTS ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    STRICT RULES:
    1. **NO NETWORK:** Do NOT use `requests`. Use `io.StringIO(file_summary)` for CSVs.
    2. **NO LAZY SIMULATIONS:** Never write `# Simulating calculation`. You MUST re-implement the actual logic found in the provided text.
    3. **SYNCHRONOUS ONLY:** No `async`/`await`.
    
    SCENARIO DETECTOR:
    
    **A. VISUALIZATION / ML:**
       - Use `matplotlib`/`sklearn`. Convert plots to Base64 string.
    
    **B. HYBRID TASK (Audio + CSV + JS):**
       - **Step 1 (Rule):** Read "AUDIO TRANSCRIPT" (e.g. "Sum > Cutoff").
       - **Step 2 (Cutoff):** - The transcript or page will mention a function (e.g. `emailNumber`).
         - **CRITICAL:** You MUST find the definition of `emailNumber` in the "IMPORTED FILE" section (utils.js) and implement it in Python 1:1.
         - **DO NOT** use `hash()` or random math. Use `hashlib.sha1` if the JS uses sha1.
       - **Step 3 (Data):** Read CSV from `file_summary` string.
       - **Step 4 (Solve):** Filter and sum. `solution = int(result)`.
    
    **C. JS LOGIC (Secret Code):**
       - Implement JS logic (from "IMPORTED FILE") in Python.
       - If `utils.js` uses `sha1`, use `hashlib.sha1`.
       - Do NOT use `demo2_key` or `7919` unless explicitly seen.
    
    **D. SIMPLE PLACEHOLDER:**
       - If sample says "anything", `solution = "anything you want"`.

    **OUTPUT:**
    - Return ONLY Python code.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL, messages=[{"role": "user", "content": prompt}], temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Extract Code
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        code = code_match.group(1) if code_match else content.replace("```python", "").replace("```", "")
        
        code = sanitize_code(code)
        print(f"DEBUG: Sanitized Python Code:\n{code}")
        
        # Variables for the script
        scope = {
            "__builtins__": __builtins__,
            "import": __import__,
            "email": STUDENT_EMAIL,
            "file_summary": file_summary, 
            "page_content": page_content
        }
        
        exec(code, scope, scope)
        
        # Final Check
        solution = scope.get("solution")
        if hasattr(solution, 'item'): solution = solution.item()
        
        return solution

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
