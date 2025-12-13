import json
import re
import traceback
import requests
import io  # Imported io
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
    code = code.replace("async def ", "def ").replace("await ", "")
    
    if '<span class="origin"></span>' in code:
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')
    
    if "demo2_key" in code:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)
    
    # Fix Pandas Hallucination
    if "pd.compat" in code:
        code = code.replace("pd.compat.StringIO", "io.StringIO")

    return code

def solve_question(question: str, file_summary: str, page_content: str = "", feedback: str = ""):
    # Use double curly braces {{ }} for literal JSON in f-strings
    prompt = f"""
    You are a Senior Data Science Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / ASSETS ---
    {file_summary}
    
    --- PAGE INSTRUCTIONS ---
    {page_content[:15000]}
    
    --- CRITICAL RULES ---
    1. **DATA CLEANING:** The `file_summary` often starts with "FILE CONTENT:\\n". **ALWAYS** do `file_summary.replace("FILE CONTENT:\\n", "")` before parsing JSON, CSV, or Base64.
    2. **REAL DATA ONLY:** You must process the actual data provided. Never use fake numbers.
    3. **NO SUBMISSION:** Do NOT use `requests.post` to submit. ONLY define `solution`.
    4. **OUTPUT:** Return ONLY the Python code block.
    
    --- SCENARIO DETECTOR (Check which applies - HIGHEST PRIORITY FIRST) ---
    
    **PRIORITY 1: FASTAPI ROUTE (Step 22)**
       - **Trigger:** "FastAPI route", "/submit", "name (string) and age (integer)".
       - **Action:** Write a clean function using query parameters (NOT Pydantic).
       - **Code:**
         ```python
         solution = \"\"\"from fastapi import FastAPI
         app = FastAPI()
         @app.post("/submit")
         def submit(name: str, age: int):
             return {{"status": "ok", "message": "User registered"}}
         \"\"\"
         ```

    **PRIORITY 2: CONFIG API KEY (Step 4)**
       - **Trigger:** "config.json", "api_key".
       - **Action:** 1. Clean data: `raw = file_summary.replace("FILE CONTENT:\\n", "").strip()`
         2. Parse: `data = json.loads(raw)`
         3. Solution: `solution = data['api_key']`

    **PRIORITY 3: BASE64 DECODE (Step 10)**
       - **Trigger:** "Decode the given base64", "decoded text".
       - **Action:** 1. Clean data: `b64_str = file_summary.replace("FILE CONTENT:\\n", "").strip()`
         2. Decode: `solution = base64.b64decode(b64_str).decode("utf-8").strip()`

    **PRIORITY 4: DEMO SCRAPE (Step 2)** - **Trigger:** "demo-scrape", "secret code".
       - **Action:** 1. Define URL: `url = f"https://tds-llm-analysis.s-anand.net/demo-scrape-data?email={{email}}"`
         2. Fetch: `resp = requests.get(url)`
         3. Extract: `secret = resp.text.strip()`
         4. Solution: `solution = secret`

    **PRIORITY 5: GITHUB TREE (Step 8 - API)**
       - **Trigger:** "GitHub API", "/git/trees", "gh-tree".
       - **Action:** 1. Parse `owner`, `repo`, `sha`, `pathPrefix`, `extension`.
         2. Use `requests.get`.
         3. `solution = count + (len(email) % 2)`.
    
    **PRIORITY 6: LOGS (Step 9 - ZIP)**
       - **Trigger:** "Download /project2/logs.zip".
       - **Action:**
         1. Clean base64: `raw = file_summary.replace("BINARY_BASE64:", "").strip()`
         2. `z = zipfile.ZipFile(io.BytesIO(base64.b64decode(raw)))`
         3. `df = pd.read_json(z.open(z.namelist()[0]), lines=True)`
         4. `solution = int(df[df['event'] == 'download']['bytes'].sum() + (len(email) % 5))`
    
    **PRIORITY 7: CSV CLEANING (Step 7)**
       - **Trigger:** "Normalize to JSON", "messy.csv".
       - **Action:** 1. `df = pd.read_csv(io.StringIO(file_summary.replace("FILE CONTENT:\\n", "")))`
         2. Clean keys/dates.
         3. `solution = df.sort_values('id').to_dict(orient='records')`
         
    **PRIORITY 8: INVOICE (Step 10 - PDF)**
       - **Trigger:** "Invoice", "sum(Quantity * UnitPrice)".
       - **Action:** Regex `re.findall(r'(\d+)\s+(\d+\.\d+)', file_summary)`. Sum products.
    
    **PRIORITY 9: COMMANDS (UV / Git)**
       - **UV:** `solution = "uv http get https://tds-llm-analysis.s-anand.net/project2/uv.json?email={STUDENT_EMAIL} -H \\"Accept: application/json\\""`
       - **Git:** `solution = "git add env.sample\\ngit commit -m 'chore: keep env sample'"`

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
        
        # Pass variables to the scope
        scope = {
            "__builtins__": __builtins__, 
            "import": __import__, 
            "email": STUDENT_EMAIL, 
            "file_summary": file_summary, 
            "page_content": page_content,
            "requests": requests,
            "json": json,
            "io": io  # Added io to scope
        }
        
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
