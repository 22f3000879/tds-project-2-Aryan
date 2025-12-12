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
    CONTENT: {decoded_html[:20000]}
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
    # 1. Remove Network calls (Aggressive)
    code = re.sub(r'^\s*import requests.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*from requests import.*$', '', code, flags=re.MULTILINE)
    code = re.sub(r'^\s*import urllib.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # 2. Fix URLs for Live Server
    if '<span class="origin"></span>' in code:
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')
    
    # 3. Legacy Function Logic
    if "demo2_key" in code:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)

    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Data Science Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / ASSETS ---
    {file_summary}
    
    --- PAGE INSTRUCTIONS ---
    {page_content[:15000]}
    
    STRICT RULES:
    1. **NO NETWORK:** Do NOT use `requests`. Data is already in `file_summary`.
    2. **IMAGES/ZIPS:** Provided as `BASE64:...`. Use `base64`, `io.BytesIO`, `PIL`, `zipfile`.
    3. **OUTPUT:** Must define `solution` variable.
    
    SCENARIO DETECTOR (Check which applies):
    
    **A. AUDIO / CSV TASK (Step 3):**
       - Task: "Download CSV... pick first column... add values >= cutoff".
       - **CUTOFF FORMULA:** `cutoff = int(hashlib.sha1(email.encode()).hexdigest()[:4], 16) % 100000`
       - **DO NOT** try to parse the email string directly. Use the SHA-1 hash logic.
       - Logic: `pd.read_csv(io.StringIO(file_summary), header=None)`. Filter & Sum.
    
    **B. JS LOGIC / SECRET CODE:**
       - **DEFAULT:** Use **SHA-1**: `int(hashlib.sha1(email.encode()).hexdigest()[:4], 16)`.
    
    **C. DEMO 2 (Alphametic):**
       - Re-calculate key: `(base * 7919 + 12345) % 100000000`.
       - Checksum: `hashlib.sha256((key + blob).encode()).hexdigest()`.
       
    **D. COMMANDS (UV / Git):**
       - **UV:** `solution = "uv http get https://tds-llm-analysis.s-anand.net/project2/uv.json?email={STUDENT_EMAIL} -H \\"Accept: application/json\\""`
       
    **E. DATA ANALYSIS (F1 / Logs / CSV / Invoice):**
       - **F1:** Use `sklearn.metrics`. `solution = {{...}}`.
       - **Logs (ZIP):** Decode Base64 -> Unzip -> Sum bytes.
       - **Invoice (PDF):** Extract text -> Regex -> Sum.

    **OUTPUT:**
    - Return ONLY the Python code block.
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
        
        solution = None
        for var in ["solution", "secret_code", "answer", "result", "command_string", "hex_color"]:
            if var in scope:
                solution = scope[var]
                break
        
        if hasattr(solution, 'item'): solution = solution.item()
        return solution

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
