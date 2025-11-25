import json
from openai import OpenAI
from .config import OPENAI_API_KEY, OPENAI_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

def analyze_task(decoded_html: str):
    """
    Step 1: Look at the decoded HTML and extract the structure.
    """
    prompt = f"""
    You are a scraper parser. 
    Analyze this HTML/Text content (which was decoded from a hidden script).
    
    Extract strictly valid JSON with these keys:
    - "question": The main question text.
    - "submit_url": The URL found in the text where the answer must be POSTed.
    - "file_url": Look for <a href="..."> links. If a file (PDF/CSV) needs to be downloaded, put the URL here. If none, null.
    
    CONTENT:
    {decoded_html[:15000]}
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        
        # Clean up markdown if LLM adds it
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"Parse Error: {e}")
        return None

def solve_question(question: str, file_summary: str):
    """
    Step 2: Answer the question based on the question text and file content.
    """
    prompt = f"""
    You are a Data Science assistant. 
    Calculate the answer to this question.
    
    QUESTION: {question}
    
    DATA CONTEXT:
    {file_summary}
    
    Return STRICT JSON format:
    {{
        "answer": <YOUR_ANSWER_HERE>
    }}
    If the answer is a number, return a number. If text, return text.
    """
    
    try:
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)["answer"]
    except Exception as e:
        print(f"Solve Error: {e}")
        return None
