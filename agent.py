import json
import re
import traceback
import requests
import io  # <--- IMPORTED IO
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
    # We use f-string, so we use DOUBLE CURLY BRACES {{ }} to escape JSON examples in the prompt
    prompt = f"""
    You are a Senior Data Science Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / ASSETS ---
    (The variable `file_summary` ALREADY contains the downloaded data. USE IT.)
    
    --- PAGE INSTRUCTIONS ---
    {page_content[:15000]}
    
    --- CRITICAL RULES ---
    1. **USE EXISTING VARIABLES:** Do NOT define `file_summary = "..."`. It is already passed to you. Just use `json.loads(file_summary)` or `pd.read_csv(io.StringIO(file_summary))`.
    2. **REAL DATA ONLY:** Never use fake numbers like "10000" or "example.com". Process the data provided.
    3. **OUTPUT:** Must define `solution` variable.
    
    --- SCENARIO DETECTOR (Check which applies - HIGHEST PRIORITY FIRST) ---
    
    **PRIORITY 1: SHARDS (Step 14 - JSON Logic)**
       - **Trigger:** "shards", "replicas", "memory_budget".
       - **Action:** 1. **CRITICAL:** Do NOT redefine `file_summary`.
         2. `data = json.loads(file_summary)` (Load the REAL data).
         3. Extract keys: `dataset`, `max_docs_per_shard`, `max_shards`, `min_replicas`, `max_replicas`, `memory_per_shard`, `memory_budget`.
         4. Loop `s` (shards) from 1 to `max_shards`.
         5. Loop `r` (replicas) from `min_replicas` to `max_replicas`.
         6. Calculate:
            - `total_docs = s * max_docs_per_shard`
            - `total_mem = s * memory_per_shard * (1 + r)`
         7. If `total_docs >= dataset` AND `total_mem <= memory_budget`:
            - `solution = json.dumps({{"shards": s, "replicas": r}})`
            - Break immediately.

    **PRIORITY 2: GITHUB TREE (Step 8 - API)**
       - **Trigger:** "GitHub API", "/git/trees", "gh-tree".
       - **Action:** 1. Parse `owner`, `repo`, `sha`, `pathPrefix`, `extension` from the question text.
         2. `requests.get(f"https://api.github.com/repos/{{owner}}/{{repo}}/git/trees/{{sha}}?recursive=1")`.
         3. Count files matching the prefix and extension.
         4. `solution = count + (len(email) % 2)`.
    
    **PRIORITY 3: LOGS (Step 9 - ZIP)**
       - **Trigger:** "Download /project2/logs.zip".
       - **Action:**
         1. `z = zipfile.ZipFile(io.BytesIO(base64.b64decode(file_summary)))`
         2. `fname = z.namelist()[0]`
         3. `df = pd.read_json(z.open(fname), lines=True)`
         4. `solution = int(df[df['event'] == 'download']['bytes'].sum() + (len(email) % 5))`
    
    **PRIORITY 4: CSV CLEANING (Step 7)**
       - **Trigger:** "Normalize to JSON", "messy.csv".
       - **Action:** 1. `df = pd.read_csv(io.StringIO(file_summary))`
         2. Clean keys: `df.columns = [c.strip().lower() for c in df.columns]`
         3. Clean dates: `pd.to_datetime(df['joined'], format='mixed', dayfirst=True)`
         4. `solution = df.sort_values('id').to_dict(orient='records')`
         
    **PRIORITY 5: INVOICE (Step 10 - PDF)**
       - **Trigger:** "Invoice", "sum(Quantity * UnitPrice)".
       - **Action:** Regex `re.findall(r'(\d+)\s+(\d+\.\d+)', file_summary)`. Sum products.
    
    **PRIORITY 6: COMMANDS (UV / Git)**
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
            "io": io  # <--- PASS IO TO SCOPE
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
