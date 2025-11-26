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
    """
    Standard safety cleaning. 
    (We keep the 7919 check as a 'Safety Net' just in case, but the new prompt should prevent it).
    """
    code = re.sub(r'^import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^import urllib.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # Safety Net: If the prompt fails, this catches the hallucination
    if "7919" in code:
        code = code.replace("7919", "1").replace("12345", "0").replace("% 100000000", "")
    if "demo2_key" in code:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)
    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Code Transpiler (JavaScript -> Python). You do NOT solve problems. You only translate code.
    
    CONTEXT:
    - Student Email: "{STUDENT_EMAIL}"
    
    SOURCE FILES (The ONLY truth):
    {file_summary}
    
    INSTRUCTIONS:
    STRICT RULES:
    1. **NO NETWORK:** Do NOT use `requests`. Use `io.StringIO(file_summary)` for CSVs.
    2. **NO HALLUCINATIONS:** Do NOT use `demo2_key` or `7919` unless explicitly in the text.
    3. **SYNCHRONOUS ONLY:** No `async`/`await`.
    4. **DONT USE ANY FORMULA FROM YOUR MEMMORY IF YOU SEE ANY SIMILAR QUESTIONS. ALWAY Trust whats provided above:** Dont be oversmart
    5. **WARNING:** Do not add math that is not in the Source File. If the Source File only does `sha1` and `slice`, then your Python must ONLY do `sha1` and `slice`
    SCENARIO DETECTOR:
    
    **A. VISUALIZATION / ML:**
       - Use `matplotlib`/`sklearn`. Convert plots to Base64 string.
    
    **B. HYBRID TASK (Audio + CSV + JS):**
       - **Step 1 (Rule):** Read "AUDIO TRANSCRIPT" (e.g. "Sum > Cutoff").
       - **Step 2 (Cutoff):** - If page mentions `emailNumber` or `cutoff`, implement JS logic from "IMPORTED FILE" 1:1.
         - **DO NOT** use `hash()` or random math. Use `hashlib.sha1`.
       - **Step 3 (Data):** Read CSV from `file_summary` string.
       - **Step 4 (Solve):** Filter and sum. `solution = int(result)`.
    
    **C. JS LOGIC (Secret Code):**
       - Implement JS logic (from "IMPORTED FILE") in Python.
       - Use `hashlib.sha1` if needed.
       - `solution = calculated_code`
    
    **D. SIMPLE PLACEHOLDER:**
       - If sample says "anything", `solution = "anything you want"`.

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
        
        # Sanitize
        code = sanitize_code(code)
        print(f"DEBUG: Generated Code:\n{code}")
        
        # Shared Scope
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL, 
                 "file_summary": file_summary, "page_content": page_content}
        
        exec(code, scope, scope)
        
        # Result Extraction
        solution = None
        for var in ["solution", "secret_code", "answer", "result"]:
            if var in scope:
                solution = scope[var]
                break
        
        if hasattr(solution, 'item'): solution = solution.item()
        return solution

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
