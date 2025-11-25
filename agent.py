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
    1. **NO NETWORK CALLS:** Do NOT use `requests`.
    2. **NO HALLUCINATIONS (CRITICAL FOR STEP 2):**
       - Do **NOT** use `demo2_key` or `7919` or `12345` unless explicitly seen in the text.
       - Look at the "IMPORTED FILE" (e.g. `utils.js`). Implement that logic EXACTLY.
    
    3. **AUDIO/CSV LOGIC (CRITICAL FOR STEP 3):**
       - If there is an "AUDIO TRANSCRIPT", read the logic from it (e.g. "Sum numbers > X").
       - If there is "CSV CONTENT", parse the text lines to get the numbers.
    
    4. **STEP 1 HANDLING:**
       - If the question/sample says `"answer": "anything"`, write: `solution = "anything you want"`.

    5. **OUTPUT:**
       - Define `solution` variable.
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
        print(f"DEBUG: Generated Python Code:\n{code}")
        
        # Execute with Shared Scope
        scope = {"__builtins__": __builtins__, "import": __import__, "email": STUDENT_EMAIL}
        exec(code, scope, scope)
        
        return scope.get("solution")

    except Exception as e:
        print(f"Solve Error: {e}")
        traceback.print_exc()
        return "Error"
