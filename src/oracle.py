import base64
import json
import time
import requests
import pandas as pd
from pathlib import Path
from rich.console import Console
from rich.progress import track

# --- CONFIG ---
# ⚠️ ACTION REQUIRED: Paste your API Key here
API_KEY = "" 
MODEL_NAME = "nvidia/nemotron-nano-12b-v2-vl:free" # ✅ VLM Model

DATA_DIR = Path("data")
QUARANTINE_DIR = DATA_DIR / "quarantine"
RECOVERED_DIR = DATA_DIR / "result"

console = Console()

class VisionOracle:
    def __init__(self):
        self.api_key = API_KEY
        self.model_name = MODEL_NAME
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/AgencyControl",
            "X-Title": "VisionOracle"
        }

    def _encode_image(self, image_path):
        """Converts image file to Base64 string for the API."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def see(self, file_path):
        """
        Sends the image to the VLM to extract text.
        NO BACKUP: Local Llama 3 cannot see images.
        """
        try:
            # 1. Encode Image
            base64_image = self._encode_image(file_path)

            # 2. Prepare Payload (Vision Format)
            payload = {
                "model": self.model_name,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Transcribe this resume image into structured markdown text. Capture all headers, dates, and bullet points accurately."},
                            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                        ]
                    }
                ]
            }

            # 3. Send to Cloud
            time.sleep(4) # Pacing
            response = requests.post(self.url, headers=self.headers, data=json.dumps(payload), timeout=60)
            
            if response.status_code == 200:
                content = response.json()['choices'][0]['message']['content']
                return content
            else:
                console.print(f"   ⚠️ [Oracle] Vision Failed ({response.status_code})")
                return None

        except Exception as e:
            console.print(f"   ⚠️ [Oracle] Connection Error: {e}")
            return None

def run_oracle_rescue():
    """
    Scans quarantine folder and tries to rescue files using Vision.
    """
    if not QUARANTINE_DIR.exists():
        console.print("[yellow]⚠️ No Quarantine folder found.[/yellow]")
        return

    # Filter for image files only
    image_exts = {'.png', '.jpg', '.jpeg'}
    files = [f for f in QUARANTINE_DIR.iterdir() if f.suffix.lower() in image_exts]
    
    if not files:
        console.print("✅ No files in quarantine to rescue.")
        return

    console.print(Panel(f"🔮 Oracle Vision Activated. Attempting to rescue {len(files)} files...", border_style="purple"))
    
    oracle = VisionOracle()
    recovered_data = []

    for f in track(files, description="Scanning Images..."):
        text = oracle.see(f)
        
        if text and len(text) > 100:
            console.print(f"   ✨ Rescued: {f.name}")
            recovered_data.append({
                "id": f.stem, # Use filename as ID
                "file_name": f.name,
                "file_type": "rescued_image",
                "extraction_method": "vision_vlm",
                "raw_text": text,
                "content_hash": "rescued_" + f.stem
            })
        else:
            console.print(f"   ❌ Could not read: {f.name}")

    # Save Recovered Data
    if recovered_data:
        df = pd.DataFrame(recovered_data)
        output_path = RECOVERED_DIR / "candidates_rescued.parquet"
        df.to_parquet(output_path, index=False)
        console.print(f"✅ Saved {len(df)} rescued candidates to {output_path}")
        return output_path  # <--- ADD THIS RETURN
    return None

if __name__ == "__main__":
    run_oracle_rescue()