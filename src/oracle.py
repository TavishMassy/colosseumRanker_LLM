import sys
import os
import json
import time
import datetime
import fitz  # PyMuPDF
import pandas as pd
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import track
from PIL import Image
from concurrent.futures import ThreadPoolExecutor

# Import configuration from your main Engine
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.engine import Engine

# --- CONFIG ---
DATA_DIR = Path("data")
QUARANTINE_DIR = DATA_DIR / "quarantine"
RESUMES_DIR = DATA_DIR / "resumes" 
RECOVERED_DIR = DATA_DIR / "result"
MAIN_DB_PATH = RECOVERED_DIR / "candidates.parquet"
BATTLE_SHEET_PATH = DATA_DIR / "job_data" / "battle_sheet.json"

console = Console()

class VisionOracle:
    def __init__(self, engine):
        self.engine = engine 

    def convert_pdf_to_image(self, pdf_path):
        """Converts first page of PDF to image with x2 zoom for OCR clarity."""
        try:
            doc = fitz.open(str(pdf_path))
            page = doc.load_page(0) 
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2)) 
            temp_path = QUARANTINE_DIR / f"{pdf_path.stem}_temp.jpg"
            pix.save(str(temp_path))
            doc.close()
            return temp_path
        except Exception as e:
            console.print(f" ❌ PDF Conversion Failed for {pdf_path.name}: {e}")
            return None

def process_single_file(f, oracle, engine, criteria):
    """Parallel Worker: Handles preparation, AI Vision, and safety checks."""
    image_to_process = f
    is_temp = False
    
    if f.suffix.lower() == '.pdf':
        image_to_process = oracle.convert_pdf_to_image(f)
        is_temp = True
    
    if not image_to_process or not image_to_process.exists():
        return (f, None)

    prompt = f"Extract factual resume data as JSON. Job Context: {json.dumps(criteria)}"
    result = engine.see(str(image_to_process), prompt)

    if is_temp and image_to_process.exists():
        image_to_process.unlink()

    if isinstance(result, list) and len(result) > 0:
        result = result[0]

    # FLEXIBLE KEY MAPPING
    if isinstance(result, dict):
        # Name Recovery
        name_val = result.get("name") or result.get("full_name") or result.get("candidate_name")
        if not name_val and "personal_information" in result:
            p_info = result["personal_information"]
            if isinstance(p_info, dict):
                name_val = p_info.get("name") or p_info.get("full_name")
        
        # Fallback Name
        if not name_val and any(result.values()):
            name_val = f"Unknown ({f.stem})"
        result["name"] = name_val

        # Contact Recovery (Email/Phone)
        if "personal_information" in result and isinstance(result["personal_information"], dict):
            p = result["personal_information"]
            result["email"] = result.get("email") or p.get("email")
            result["phone"] = result.get("phone") or p.get("phone")

    return (f, result)

def run_oracle_rescue():
    if not QUARANTINE_DIR.exists(): return

    engine = Engine()
    oracle = VisionOracle(engine)

    criteria = {"role": "General", "must_haves": []}
    if BATTLE_SHEET_PATH.exists():
        with open(BATTLE_SHEET_PATH, 'r') as f:
            data = json.load(f)
            criteria = data[0] if isinstance(data, list) else data
    
    files = [f for f in QUARANTINE_DIR.iterdir() if f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.pdf'} and "_temp" not in f.name]

    if not files:
        console.print("[dim]✅ Quarantine is empty.[/dim]")
        return

    console.print(Panel(f"🔮 Oracle Parallel Core: Rescuing {len(files)} files...", border_style="purple"))
    rescued_candidates = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(process_single_file, f, oracle, engine, criteria) for f in files]
        
        for future in track(futures, description="Parallel Processing..."):
            try:
                f_original, result = future.result()
            except Exception as e:
                console.print(f"[red]❌ Thread Crash: {e}[/red]")
                continue

            # Deduplication
            txt_filename = f"{f_original.stem}.txt"
            txt_path = RESUMES_DIR / txt_filename
            
            if txt_path.exists():
                console.print(f" [dim]♻️  {f_original.name} already exists. Cleaning quarantine.[/dim]")
                f_original.unlink()
                continue

            if not result or not result.get("name"):
                console.print(f"[yellow]⚠️ Data Error: {f_original.name} has no valid name field.[/yellow]")
                continue

            # --- HIGH-FIDELITY EXTRACTION ---
            summary = result.get('summary') or result.get('objective') or "N/A"
            exp = result.get('experience') or result.get('work_experience') or "N/A"
            skills = result.get('skills') or result.get('technical_skills') or []
            links = result.get('links') or result.get('portfolio') or result.get('social_media') or []

            # Format list-based data safely
            skills_str = ', '.join(skills) if isinstance(skills, list) else str(skills)
            links_str = ', '.join(links) if isinstance(links, list) else str(links)

            resume_text = (
                f"Candidate Name: {result.get('name')}\n"
                f"Location: {result.get('location', 'N/A')}\n"
                f"Email: {result.get('email', 'N/A')}\n"
                f"Phone: {result.get('phone', 'N/A')}\n"
                f"Links: {links_str}\n\n"
                f"--- PROFESSIONAL SUMMARY ---\n{summary}\n\n"
                f"--- EXPERIENCE ---\n{exp}\n\n"
                f"--- SKILLS ---\n{skills_str}"
            )

            try:
                with open(txt_path, 'w', encoding='utf-8') as txt_file:
                    txt_file.write(resume_text)
                
                f_original.unlink() 
                
                rescued_candidates.append({
                    "id": f_original.stem,
                    "file_name": txt_path.name,
                    "name": result.get("name"),
                    "safe_text": resume_text,
                    "extraction_method": "parallel_vision_engine_flexible",
                    "contact_info": {
                        "email": result.get("email"),
                        "phone": result.get("phone"),
                        "links": links
                    },
                    "meta_role": result.get('current_role'),
                    "meta_yoe": result.get('years_experience')
                })
            except Exception as e:
                console.print(f"   ❌ Save Failed for {f_original.name}: {e}")

    # Final DB Sync
    if rescued_candidates:
        new_df = pd.DataFrame(rescued_candidates)
        if MAIN_DB_PATH.exists():
            final_df = pd.concat([pd.read_parquet(MAIN_DB_PATH), new_df], ignore_index=True)
        else:
            final_df = new_df

        RECOVERED_DIR.mkdir(parents=True, exist_ok=True)
        final_df.to_parquet(MAIN_DB_PATH, index=False)
        console.print(f"[bold green]✅ Oracle Complete. Daily Tokens Used: {engine.usage['total_tokens']}[/bold green]")

if __name__ == "__main__":
    run_oracle_rescue()