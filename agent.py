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

def sanitize_code(code: str, context: str):
    """
    Cleans code and removes hallucinations based on context.
    """
    # 1. Remove Network stuff
    code = re.sub(r'^import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^import urllib.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # 2. SURGICAL REMOVAL OF HALLUCINATIONS
    # If the code tries to do the "7919" math, but "7919" isn't in the source files...
    if "7919" in code and "7919" not in context:
        print("DEBUG: Detecting hallucinated math. Removing it...")
        # Replace the math line with a simple assignment
        # Regex matches: variable = (base * 7919 ...
        code = re.sub(r'(\w+)\s*=\s*\(.*?\*\s*7919.*', r'\1 = email_number(email)', code)
        
    # 3. Function Replacement
    if "demo2_key" in code and "demo2_key" not in context:
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
    1. **SCENARIO A (Anything):** If JSON sample says "answer": "anything", write: `solution = "anything you want"`
    
    2. **SCENARIO B (JS Logic):** - Implement logic from "IMPORTED FILE" 1:1.
       - **DO NOT** use `demo2_key` or `7919` unless explicitly seen in the text.
       - Just return the result of `emailNumber()`.
    
    3. **SCENARIO C (Audio/CSV):**
       - Read "AUDIO TRANSCRIPT" for the rule.
       - Use `io.StringIO(file_summary)` for CSVs.
       - `solution = int(result)`.

    **OUTPUT:**
    - **MUST** define a variable named `solution` at the end.
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
        
        # --- INTELLIGENT SANITIZATION ---
        # Pass the file_summary as context so we know what is real and what is fake
        code = sanitize_code(code, file_summary)
        print(f"DEBUG: Final Python Code:\n{code}")
        
        # Shared Scope
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL, 
                 "file_summary": file_summary, "page_content": page_content}
        
        exec(code, scope, scope)
        
        # --- SAFETY NET: Find the answer if 'solution' is missing ---
        if "solution" in scope:
            return scope["solution"]
        elif "secret_code" in scope:
            print("DEBUG: 'solution' missing, using 'secret_code'")
            return scope["secret_code"]
        elif "answer" in scope:
            print("DEBUG: 'solution' missing, using 'answer'")
            return scope["answer"]
        elif "result" in scope:
            print("DEBUG: 'solution' missing, using 'result'")
            return scope["result"]
        else:
            print("ERROR: No solution variable found.")
            return None

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
