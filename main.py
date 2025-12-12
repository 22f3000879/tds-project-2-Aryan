from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
import httpx
import re
import asyncio
from urllib.parse import urljoin
from config import STUDENT_EMAIL, STUDENT_SECRET
from utils import fetch_and_decode_page, parse_file_content
from agent import analyze_task, solve_question

app = FastAPI()

async def run_quiz_process(start_url: str):
    current_url = start_url
    step_count = 0
    base_domain = "https://tds-llm-analysis.s-anand.net"
    if "localhost" in start_url or "127.0.0.1" in start_url:
        base_domain = "http://127.0.0.1:8787"
    
    while current_url and step_count < 15:
        print(f"\n--- STEP {step_count + 1} processing {current_url} ---")
        
        try:
            decoded_text = await fetch_and_decode_page(current_url)
        except Exception as e:
            print(f"Failed to fetch page: {e}")
            break
        
        task_data = analyze_task(decoded_text)
        if not task_data:
            print("Failed to parse task.")
            break
            
        print(f"Task Found: {task_data}")
        
        file_summary = "No files."
        if task_data.get("file_url"):
            raw_f_url = task_data["file_url"]
            f_url = re.sub(r'<[^>]+>', '', raw_f_url).strip()
            
            if f_url:
                if "example.com" in f_url:
                    f_url = f_url.replace("https://example.com", base_domain).replace("http://example.com", base_domain)
                if not f_url.startswith("http"): 
                    f_url = urljoin(base_domain, f_url)
                print(f"Downloading file: {f_url}")
                file_summary = parse_file_content(f_url)

        submit_url = urljoin(base_domain, "/submit")

        attempts = 0
        success = False
        last_response_json = {}  # Store the last response to check for "pity URLs"
        
        while attempts < 5 and not success:
            answer = solve_question(task_data["question"], file_summary, decoded_text)
            print(f"Calculated Answer (Attempt {attempts+1}): {answer}")
            
            payload = {
                "email": STUDENT_EMAIL,
                "secret": STUDENT_SECRET,
                "url": current_url,
                "answer": answer
            }
            
            try:
                print(f"Submitting to {submit_url}")
                async with httpx.AsyncClient() as client:
                    resp = await client.post(submit_url, json=payload, timeout=30)
                    
                    if resp.status_code != 200:
                        print(f"Server Error {resp.status_code}: {resp.text[:200]}")
                    
                    try:
                        last_response_json = resp.json()
                        print(f"Submission Result: {last_response_json}")
                        
                        if last_response_json.get("correct"):
                            success = True
                        else:
                            print(f"Wrong Answer. Retrying... Reason: {last_response_json.get('reason')}")
                            attempts += 1
                            await asyncio.sleep(1)
                    except:
                        print(f"Failed to parse JSON. Raw: {resp.text[:100]}")
                        attempts += 1
                        
            except Exception as e:
                print(f"Submission failed: {e}")
                attempts += 1
        
        # --- NEW LOGIC: Proceed if we have a URL, even if we failed ---
        next_url = last_response_json.get("url")
        
        if success and next_url:
            if not next_url.startswith("http"): next_url = urljoin(base_domain, next_url)
            current_url = next_url
            step_count += 1
        elif not success and next_url:
            print(">>> FAILED 3 attempts, but server provided a NEXT URL. Proceeding anyway! <<<")
            if not next_url.startswith("http"): next_url = urljoin(base_domain, next_url)
            current_url = next_url
            step_count += 1
        else:
            print("Failed step after 5 attempts and no next URL provided.")
            break

@app.post("/")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    try: data = await request.json()
    except: raise HTTPException(status_code=400, detail="Invalid JSON")
    if data.get("secret") != STUDENT_SECRET: raise HTTPException(status_code=403, detail="Invalid Secret")
    background_tasks.add_task(run_quiz_process, data.get("url"))
    return {"message": "Quiz processing started", "status": "ok"}

@app.get("/")
def health_check():
    return {"status": "active", "student": STUDENT_EMAIL}
