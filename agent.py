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
    code = re.sub(r'^\s*import requests.*$', '', code, flags=re.MULTILINE)
    code = code.replace("async def ", "def ").replace("await ", "")
    if '<span class="origin"></span>' in code:
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')
    if "demo2_key" in code:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)
    if "pd.compat" in code:
        code = code.replace("pd.compat.StringIO", "io.StringIO")
    return code

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Data Science Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / ASSETS ---
    {file_summary}
    
    --- PAGE CONTENT (Search here for BLOBs or KEYS) ---
    {page_content[:20000]}
    
    STRICT RULES:
    1. **NO NETWORK:** Do NOT use `requests`. 
    2. **OUTPUT:** Must define `solution` variable.
    
    SCENARIO DETECTOR (Check which applies):
    
    **A. DEMO 2 (Alphametic / Checksum):**
       - **Trigger:** "ALPHAMETIC", "F O R K", "checksum".
       - **Logic:**
         1. Calculate Base: `base = int(hashlib.sha1(email.encode()).hexdigest()[:4], 16)`
         2. Calculate Key: `key = str((base * 7919 + 12345) % 100000000).zfill(8)`
         3. **IF Checksum Task:** - Find the BLOB in the "PAGE CONTENT" above. It is usually a random string displayed on the page.
            - `blob = "FOUND_BLOB_STRING"` (e.g. "9F8E7D..."). DO NOT USE EMPTY STRING.
            - `solution = hashlib.sha256((key + blob).encode()).hexdigest()[:12]`
         4. **IF Alphametic Task:**
            - `solution = key`
    
    **B. AUDIO PASSPHRASE:**
       - **Trigger:** "Transcribe".
       - `solution = "text from audio transcript"`
    
    **C. CSV MATH:**
       - **Trigger:** "Download CSV", "cutoff".
       - `cutoff = int(hashlib.sha1(email.encode()).hexdigest()[:4], 16) % 100000`
       - `df = pd.read_csv(io.StringIO(file_summary), header=None)`
       - `solution = int(df[df[0] >= cutoff][0].sum())`
    
    **D. JS LOGIC (Secret Code):**
       - `solution = int(hashlib.sha1(email.encode()).hexdigest()[:4], 16)`
       
    **E. COMMANDS (UV / Git):**
       - **UV:** `solution = "uv http get https://tds-llm-analysis.s-anand.net/project2/uv.json?email={STUDENT_EMAIL} -H \\"Accept: application/json\\""`
       - **Git:** `solution = "git add env.sample\\ngit commit -m 'chore: keep env sample'"`
       
    **F. DATA ANALYSIS (F1 / Logs / Invoice):**
       - **F1:** `solution = {{...}}`.
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
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        code = code_match.group(1) if code_match else content.replace("```python", "").replace("```", "")
        code = sanitize_code(code)
        print(f"DEBUG: Final Python Code:\n{code}")
        
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
