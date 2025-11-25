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

def solve_question(question: str, file_summary: str, page_content: str = ""):
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS / TRANSCRIPTS ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    STRICT INSTRUCTIONS:
    1. **IMPORTS:** You can use `pandas`, `numpy`, `scikit-learn`, `matplotlib.pyplot`, `seaborn`.
    
    2. **SCENARIO: VISUALIZATION (Charts/Plots):**
       - If asked to plot/visualize:
         1. Create plot with `plt.figure()`.
         2. Save to buffer:
            ```python
            import io, base64
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            solution = "data:image/png;base64," + base64.b64encode(buf.read()).decode('utf-8')
            ```
    
    3. **SCENARIO: ANALYSIS / ML:**
       - If asked for clustering/regression, use `sklearn`.
       - Example: `from sklearn.linear_model import LinearRegression`.
    
    4. **SCENARIO: SECRET CODE (JS Logic):**
       - Translate JS logic 1:1. Do NOT use `demo2_key` or `7919` unless seen in text.
    
    5. **SCENARIO: CSV/AUDIO:**
       - Parse CSV, apply rules from Audio transcript.
       - **CRITICAL:** For simple numbers, `solution = int(result)`.

    6. **OUTPUT:**
       - Define variable `solution`.
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
        print(f"DEBUG: Generated Python Code:\n{code}")
        
        # Execute
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL}
        exec(code, scope, scope)
        
        return scope.get("solution")

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
