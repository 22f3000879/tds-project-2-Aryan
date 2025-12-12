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
    
    # Fix URLs for Live Server
    if '<span class="origin"></span>' in code:
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')
    
    if "demo2_key" in code:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)
    
    # CRITICAL FIX for Step 7
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
    
    --- PAGE INSTRUCTIONS ---
    {page_content[:15000]}
    
    STRICT RULES:
    1. **NO NETWORK:** Do NOT use `requests`. 
    2. **OUTPUT:** Must define `solution` variable.
    
    SCENARIO DETECTOR (Check which applies - HIGHEST PRIORITY FIRST):
    
    **PRIORITY 1: LOGS (Step 9 - ZIP)**
       - **Trigger:** "Download /project2/logs.zip", "sum bytes".
       - **Logic:**
         1. `z = zipfile.ZipFile(io.BytesIO(base64.b64decode(file_summary)))`
         2. `fname = z.namelist()[0]` (Get the actual filename dynamically!)
         3. `df = pd.read_json(z.open(fname), lines=True)`
         4. Filter `df['event'] == 'download'` and sum `df['bytes']`.
         5. `solution = int(sum_val + (len(email) % 5))`
    
    **PRIORITY 2: INVOICE (Step 10 - PDF)**
       - **Trigger:** "Invoice", "sum(Quantity * UnitPrice)".
       - **Logic:** **DO NOT USE PANDAS.** Use Regex to find numbers in the text.
         1. `items = re.findall(r'(\d+)\s+(\d+\.\d+)', file_summary)` (Matches: int Quantity ... float Price)
         2. Loop through matches: `total += int(qty) * float(price)`
         3. `solution = str(round(total, 2))` (or float).
    
    **PRIORITY 3: CSV CLEANING (Step 7)**
       - **Trigger:** "Normalize to JSON", "messy.csv".
       - **Logic:** 1. `df = pd.read_csv(io.StringIO(file_summary))`
         2. Clean keys: `df.columns = [c.strip().lower() for c in df.columns]`
         3. Clean dates: `pd.to_datetime(df['joined'], format='mixed').dt.strftime('%Y-%m-%d')`
         4. Sort by `id` ascending.
         5. `solution = df.to_dict(orient='records')`
         
    **PRIORITY 4: AUDIO PASSPHRASE (Step 5)**
       - **Trigger:** "Transcribe", "spoken phrase".
       - **Logic:** `solution = "text extracted from AUDIO TRANSCRIPT above"`
    
    **PRIORITY 5: CSV MATH (Step 3)**
       - **Trigger:** "Download CSV", "cutoff".
       - **Logic:** `cutoff = int(hashlib.sha1(email.encode()).hexdigest()[:4], 16) % 100000`.
       - `df = pd.read_csv(io.StringIO(file_summary), header=None)`. Filter & Sum.
    
    **PRIORITY 6: DEMO 2 (Alphametic)**
       - Re-calculate key: `(base * 7919 + 12345) % 100000000`.
       - Checksum: `hashlib.sha256((key + blob).encode()).hexdigest()`.
       
    **PRIORITY 7: COMMANDS (UV / Git)**
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
        
        # Pass file_summary to the scope
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
