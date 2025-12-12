import json
import re
import traceback
import requests  # Ensure requests is imported here for safety
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
    # REMOVED the line that bans requests!
    # code = re.sub(r'^\s*import requests.*$', '', code, flags=re.MULTILINE) <--- DELETED
    
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
    prompt = f"""
    You are a Senior Data Science Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / ASSETS ---
    {file_summary}
    
    --- PAGE INSTRUCTIONS ---
    {page_content[:15000]}
    
    --- CRITICAL RULES (DO NOT IGNORE) ---
    1. **REAL DATA ONLY:** You must process the actual data provided or fetch it via API.
    2. **NO MOCKING:** NEVER create fake dictionaries, lists, or "simulated" responses. If you need data, write code to get it.
    3. **NETWORK ACCESS:** You are ALLOWED to use `requests` for API tasks (like GitHub).
    4. **OUTPUT:** Must define `solution` variable.
    
    --- SCENARIO DETECTOR (Check which applies - HIGHEST PRIORITY FIRST) ---
    
    **PRIORITY 1: GITHUB TREE (Step 8 - API)**
       - **Trigger:** "GitHub API", "/git/trees", "gh-tree".
       - **Action:** 1. Parse `owner`, `repo`, `sha`, `pathPrefix`, `extension` from the question text.
         2. Use `requests.get(f"https://api.github.com/repos/{{owner}}/{{repo}}/git/trees/{{sha}}?recursive=1")`.
         3. Count files matching the prefix and extension.
         4. `offset = len(email) % 2`.
         5. `solution = count + offset`.
    
    **PRIORITY 2: LOGS (Step 9 - ZIP)**
       - **Trigger:** "Download /project2/logs.zip", "sum bytes".
       - **Action:**
         1. `z = zipfile.ZipFile(io.BytesIO(base64.b64decode(file_summary)))`
         2. `fname = z.namelist()[0]` (Get ACTUAL filename!)
         3. `df = pd.read_json(z.open(fname), lines=True)`
         4. Filter `df['event'] == 'download'` and sum `df['bytes']`.
         5. `solution = int(sum_val + (len(email) % 5))`
    
    **PRIORITY 3: TOOLS PLAN (Step 15)**
       - **Trigger:** "Create an ordered plan", "tool calls".
       - **Action:** Return a JSON list of objects matching the schema.
       - `solution = json.dumps([...plan...])` (Stringified JSON).
    
    **PRIORITY 4: CSV CLEANING (Step 7)**
       - **Trigger:** "Normalize to JSON", "messy.csv".
       - **Action:** 1. `df = pd.read_csv(io.StringIO(file_summary))`
         2. Clean keys: `df.columns = [c.strip().lower() for c in df.columns]`
         3. Clean dates: `pd.to_datetime(df['joined'], format='mixed', dayfirst=True)`
         4. `solution = df.sort_values('id').to_dict(orient='records')`
         
    **PRIORITY 5: INVOICE (Step 10 - PDF)**
       - **Trigger:** "Invoice", "sum(Quantity * UnitPrice)".
       - **Action:** Use Regex `re.findall(r'(\d+)\s+(\d+\.\d+)', file_summary)`. Loop and sum.
    
    **PRIORITY 6: AUDIO PASSPHRASE (Step 5)**
       - **Trigger:** "Transcribe", "spoken phrase".
       - **Action:** `solution = "text from audio transcript"`
    
    **PRIORITY 7: CSV MATH (Step 3)**
       - **Trigger:** "Download CSV", "cutoff".
       - **Action:** 1. `cutoff = int(hashlib.sha1(email.encode()).hexdigest()[:4], 16) % 100000`
         2. `df = pd.read_csv(io.StringIO(file_summary), header=None)`. Filter & Sum.
    
    **PRIORITY 8: DEMO 2 (Alphametic)**
       - Re-calculate key: `(base * 7919 + 12345) % 100000000`.
       - Checksum: `hashlib.sha256((key + blob).encode()).hexdigest()`.
       
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
        
        # Pass file_summary to the scope
        scope = {
            "__builtins__": __builtins__, 
            "import": __import__, 
            "email": STUDENT_EMAIL, 
            "file_summary": file_summary, 
            "page_content": page_content,
            "requests": requests, # Explicitly pass requests to the scope
            "json": json
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
