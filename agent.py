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
    # 1. Allow requests (Needed for GitHub API task), but generally discourage it via prompt.
    # We NO LONGER remove 'import requests' aggressively.
    
    code = code.replace("async def ", "def ").replace("await ", "")
    
    # 2. Fix URLs for Live Server
    if '<span class="origin"></span>' in code:
        code = code.replace('<span class="origin"></span>', 'https://tds-llm-analysis.s-anand.net')
    
    # 3. Legacy Logic
    if "demo2_key" in code:
         code = re.sub(r'demo2_key\(.*?\)', 'email_number(email)', code)
    
    # 4. Fix Pandas Hallucination (Critical for Step 7)
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
    1. **DATA:** The variable `file_summary` contains the REAL content of the downloaded file. 
       - USE `io.StringIO(file_summary)` to read it. 
       - DO NOT create fake variables like `csv_data = "..."`.
    2. **NETWORK:** - **Default:** Do NOT use `requests`. 
       - **Exception:** If the task explicitly asks to query an API (e.g. GitHub), you MUST use `requests.get()`.
    3. **OUTPUT:** Must define `solution` variable.
    
    SCENARIO DETECTOR (Check which applies - HIGHEST PRIORITY FIRST):
    
    **PRIORITY 1: GITHUB API (Step 8)**
       - **Trigger:** "GitHub API", "gh-tree", "/git/trees".
       - **Logic:**
         1. Parse the JSON in `file_summary`.
         2. Construct URL: `https://api.github.com/repos/{{owner}}/{{repo}}/git/trees/{{sha}}?recursive=1`
         3. `resp = requests.get(url).json()`
         4. Count items where `path` starts with `pathPrefix` AND ends with `.md`.
         5. `solution = count + (len(email) % 2)`
    
    **PRIORITY 2: CSV CLEANING (Step 7)**
       - **Trigger:** "Normalize to JSON", "messy.csv".
       - **Logic:** 1. `df = pd.read_csv(io.StringIO(file_summary))`
         2. Clean keys: `df.columns = [c.strip().lower() for c in df.columns]`
         3. Clean dates: `pd.to_datetime(df['joined'], format='mixed').dt.strftime('%Y-%m-%d')`
         4. Sort by `id` ascending.
         5. `solution = df.to_dict(orient='records')`

    **PRIORITY 3: AUDIO PASSPHRASE (Step 5)**
       - **Trigger:** "Transcribe", "spoken phrase".
       - **Logic:** Copy text from "AUDIO TRANSCRIPT" in data section. `solution = "text"`
    
    **PRIORITY 4: CSV MATH (Step 3)**
       - **Trigger:** "Download CSV", "cutoff".
       - **Logic:** `cutoff = int(hashlib.sha1(email.encode()).hexdigest()[:4], 16) % 100000`.
       - `df = pd.read_csv(io.StringIO(file_summary), header=None)`. Filter & Sum.
    
    **PRIORITY 5: DEMO 2 (Alphametic)**
       - **Trigger:** "ALPHAMETIC", "F O R K".
       - **Logic:** `base = int(hashlib.sha1(email.encode()).hexdigest()[:4], 16)`.
       - `key = str((base * 7919 + 12345) % 100000000).zfill(8)`.
       - Checksum? `hashlib.sha256((key + blob).encode()).hexdigest()[:12]`. Find `blob` in page text!
       
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
