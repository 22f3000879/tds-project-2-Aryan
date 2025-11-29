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
    Cleans code and NEUTRALIZES hallucinations and HTML artifacts.
    """
    # 1. Remove Network stuff
    code = re.sub(r'^import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^import urllib.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # 2. FIX URL ARTIFACTS (The Fix for Step 2)
    # The LLM often copies <span class="origin"></span> into the string.
    # We replace it with the actual domain.
    if '<span class="origin"></span>' in code:
        print("DEBUG: Replacing HTML tag in URL with actual domain.")
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')
        
    # 3. NEUTRALIZE HALLUCINATED MATH
    if "7919" in code:
        code = code.replace("7919", "1")
        code = code.replace("12345", "0")
        code = code.replace("% 100000000", "")
        
    # 4. Function Replacement
    if "demo2_key" in code:
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
    2. **NO HALLUCINATIONS:** Do NOT use `demo2_key` or `7919` unless explicitly in the text.
    3. **SYNCHRONOUS ONLY:** No `async`/`await`.
    
    SCENARIO DETECTOR:
    
    **A. COMMAND GENERATION (uv/pip):**
       - If asked to craft a command (e.g. `uv http get`):
       - `solution = "the_exact_command_string"`
       - Ensure you replace `<span class="origin"></span>` with `https://tds-llm-analysis.s-anand.net` if needed (or the sanitizer will do it).
    
    **B. HYBRID TASK (Audio + CSV + JS):**
       - **Step 1 (Rule):** Read "AUDIO TRANSCRIPT".
       - **Step 2 (Cutoff):** If page mentions `emailNumber` or `cutoff`, implement the JS logic found in "IMPORTED FILE" 1:1.
       - **Step 3 (Data):** Read CSV from `file_summary` using `pd.read_csv(io.StringIO(file_summary))`.
       - **Step 4 (Solve):** Filter and sum. `solution = int(result)`.
    
    **C. JS LOGIC (Secret Code):**
       - Implement JS logic (from "IMPORTED FILE") in Python.
       - Use `hashlib.sha1` if needed.
       - Do NOT use `demo2_key` or `7919` unless seen in text.
    
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
        
        # --- SANITIZE ---
        code = sanitize_code(code)
        print(f"DEBUG: Final Python Code:\n{code}")
        
        # Shared Scope
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL, 
                 "file_summary": file_summary, "page_content": page_content}
        
        exec(code, scope, scope)
        
        # --- SAFETY NET ---
        solution = None
        for var in ["solution", "secret_code", "answer", "result"]:
            if var in scope:
                solution = scope[var]
                break
        
        # Fix numpy types
        if hasattr(solution, 'item'): 
            solution = solution.item()
            
        return solution

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
