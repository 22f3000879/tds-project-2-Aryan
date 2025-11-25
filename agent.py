def solve_question(question: str, file_summary: str, page_content: str = ""):
    """
    Solves the question by generating and EXECUTING Python code.
    """
    prompt = f"""
    You are a Python Expert. Write a Python script to calculate the answer.
    
    QUESTION: {question}
    Student Email: "{STUDENT_EMAIL}"
    
    --- DATA / SCRIPTS (JS Logic) ---
    {file_summary}
    
    --- PAGE CONTENT ---
    {page_content[:10000]}
    
    STRICT INSTRUCTIONS:
    1. **NO NETWORK CALLS:** Do NOT use `requests`. Calculate everything locally.
    2. **TRANSLATE LOGIC:** - Read the JavaScript functions in the provided text.
       - Implement the EXACT SAME logic in Python.
       - If the JS does `(x * 7919) % 100`, your Python must do `(x * 7919) % 100`.
    3. **OUTPUT:**
       - Define a variable `solution` with the final answer.
       - Return ONLY the Python code block.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Extract Python Code
        code_match = re.search(r"```python\n(.*?)```", content, re.DOTALL)
        if code_match:
            code = code_match.group(1)
        else:
            code = content.replace("```python", "").replace("```", "")
            
        print(f"DEBUG: Generated Python Code:\n{code}")
        
        # --- THE FIX: SHARED SCOPE ---
        # We create ONE dictionary for both globals and locals.
        # This allows functions to call each other.
        execution_scope = {
            "__builtins__": __builtins__,
            "import": __import__,
            "email": STUDENT_EMAIL
        }
        
        try:
            # Pass execution_scope as BOTH globals and locals
            exec(code, execution_scope, execution_scope)
        except Exception as e:
            print(f"Execution Error: {e}")
            traceback.print_exc()
            return "Error executing code"
            
        # Retrieve Solution
        answer = execution_scope.get("solution")
        print(f"DEBUG: Execution Result (solution): {answer}")
        
        return answer

    except Exception as e:
        print(f"Solve Error: {e}")
        return "Error"
