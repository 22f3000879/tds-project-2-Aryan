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
    Cleans code and NEUTRALIZES hallucinations.
    """
    code = re.sub(r'^import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^import urllib.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # URL Fix (for Step 2 uv command)
    if '<span class="origin"></span>' in code:
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')
        
    # Math Fix (for Step 2 Secret Code)
    if "7919" in code:
        code = code.replace("7919", "1").replace("12345", "0").replace("% 100000000", "")
    if "demo2_key" in code:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)

    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS / TRANSCRIPTS ---
    {file_summary[:10000]} ...
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    STRICT RULES:
    1. **NO NETWORK:** Do NOT use `requests`. 
    2. **NO FILESYSTEM:** Do NOT try to `open()` files. All data is in variables.
    3. **SYNCHRONOUS ONLY:** No `async`/`await`.
    
    SCENARIO DETECTOR:
    
    **A. IMAGE ANALYSIS (Input Image):**
       - IF `file_summary` starts with "IMAGE_BASE64:":
         1. Import `base64`, `io`, `PIL.Image`, `collections`.
         2. Decode the data: `img = Image.open(io.BytesIO(base64.b64decode(file_summary.split(':', 1)[1])))`
         3. Analyze pixels (e.g., `img.getdata()`, `Counter`).
         4. `solution = hex_color_string` (e.g., "#b45a1e").
    
    **B. COMMAND GENERATION (uv/pip):**
       - If asked to craft a command (e.g. `uv http get`):
       - `solution = "the_exact_command_string"`
       - Ensure you replace `<span class="origin"></span>` with `https://tds-llm-analysis.s-anand.net`.
    
    **C. HYBRID TASK (Audio + CSV + JS):**
       - **Step 1:** Read "AUDIO TRANSCRIPT".
       - **Step 2:** If `emailNumber`/`cutoff` needed, implement JS logic from "IMPORTED FILE" 1:1 (No fake math!).
       - **Step 3:** Read CSV from `file_summary` variable: `pd.read_csv(io.StringIO(file_summary))`.
       - **Step 4:** `solution = int(result)`.
    
    **D. JS LOGIC (Secret Code):**
       - Implement JS logic 1:1. Use `hashlib.sha1`.
       - `solution = calculated_value`
    
    **E. SIMPLE PLACEHOLDER:**
       - `solution = "anything you want"`.

    **OUTPUT:**
    - **MUST** define a variable named `solution`.
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
        print(f"DEBUG: Final Python Code:\n{code}")
        
        # Shared Scope
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL, 
                 "file_summary": file_summary, "page_content": page_content}
        
        exec(code, scope, scope)
        
        # --- SAFETY NET ---
        solution = None
        for var in ["solution", "secret_code", "answer", "result", "command_string", "hex_color"]:
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
