from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
import httpx
import re
import asyncio
from urllib.parse import urljoin
from config import STUDENT_EMAIL, STUDENT_SECRET
from utils import fetch_and_decode_page, parse_file_content
from agent import analyze_task, solve_question

app = FastAPI()

def clean_extracted_url(url: str):
    if not url: return None
    clean = re.sub(r'<[^>]+>', '', url)
    return clean.strip()

async def run_quiz_process(start_url: str):
    current_url = start_url
    step_count = 0
    
    while current_url and step_count < 15:
        print(f"\n--- STEP {step_count + 1} processing {current_url} ---")
        
        # 1. Fetch & Decode
        try:
            decoded_text = await fetch_and_decode_page(current_url)
        except Exception as e:
            print(f"Failed to fetch page: {e}")
            break
        
        # 2. Parse Task
        task_data = analyze_task(decoded_text)
        if not task_data:
            print("Failed to parse task.")
            break
            
        print(f"Task Found: {task_data}")
        
        # 3. Download Files
        file_summary = "No files."
        if task_data.get("file_url"):
            raw_f_url = task_data["file_url"]
            f_url = clean_extracted_url(raw_f_url)
            if f_url:
                if not f_url.startswith("http"): 
                    f_url = urljoin(current_url, f_url)
                print(f"Downloading file: {f_url}")
                file_summary = parse_file_content(f_url)

        # 4. Determine Submit URL (CRITICAL FIX)
        raw_submit_url = task_data.get("submit_url")
        submit_url = clean_extracted_url(raw_submit_url)
        
        # Logic: If submit_url is missing OR looks like the current page, default to /submit
        if not submit_url or submit_url in current_url or "project2-uv" in submit_url:
            print("DEBUG: Submit URL looks wrong or missing. Defaulting to /submit")
            submit_url = "/submit"
            
        if not submit_url.startswith("http"): 
            # Ensure we use the base domain from the current_url
            base_domain = "/".join(current_url.split("/")[:3]) # https://domain.com
            submit_url = urljoin(base_domain, submit_url)

        # 5. Solve & Submit (Retry Loop)
        attempts = 0
        success = False
        
        while attempts < 3 and not success:
            answer = solve_question(task_data["question"], file_summary, decoded_text)
            print(f"Calculated Answer (Attempt {attempts+1}): {answer}")
            
            payload = {
                "email": STUDENT_EMAIL,
                "secret": STUDENT_SECRET,
                "url": current_url,
                "answer": answer
            }
            
            try:
                print(f"Submitting to {submit_url}...")
                async with httpx.AsyncClient() as client:
                    resp = await client.post(submit_url, json=payload, timeout=30)
                    
                    # --- DEBUGGING RESPONSE ---
                    if resp.status_code != 200:
                        print(f"Server Error {resp.status_code}: {resp.text[:200]}")
                    
                    try:
                        result = resp.json()
                        print(f"Submission Result: {result}")
                        
                        if result.get("correct"):
                            success = True
                            if result.get("url"):
                                current_url = result["url"]
                                step_count += 1
                            else:
                                print("Quiz Completed Successfully!")
                                return
                        else:
                            print(f"Wrong Answer. Retrying... Reason: {result.get('reason')}")
                            attempts += 1
                            await asyncio.sleep(1)
                    except:
                        print(f"Failed to parse JSON response. Raw text: {resp.text[:200]}")
                        attempts += 1
                        
            except Exception as e:
                print(f"Submission failed: {e}")
                attempts += 1
        
        if not success:
            print("Failed step after 3 attempts.")
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
