import json
import sys
import os
import random
import time
import datetime
import threading
from pathlib import Path
from google import genai
from google.genai import types

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.backup_engine import LocalEngine 

# --- ENGINE CONFIGURATION ---
API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = "gemini-flash-latest"
VLM_NAME = "gemini-flash-lite-latest"
TOKEN_LIMIT = 800000
USAGE_FILE = Path("data/usage_log.json")
# ----------------------------

class Engine:
    def __init__(self):
        if not API_KEY:
            raise ValueError("No API Key found. Please set GEMINI_API_KEY.")
            
        self.api_key = API_KEY
        self.backup = LocalEngine()
        self.is_cloud_alive = True
        self.lock = threading.Lock()

        self.usage = self._load_usage()
        print(f"   📊 [System] Daily Usage: {self.usage['total_tokens']}/{TOKEN_LIMIT} (Date: {self.usage['date']})")

        if not self.api_key or "AIza" not in self.api_key:
            print("   ⚠️ [System] Invalid or Missing Google API Key. Disabling Cloud.")
            self.is_cloud_alive = False
        else:
            try:
                self.client = genai.Client(
                    api_key=self.api_key)
                if self.is_cloud_alive:
                    print(f"   ✅ [System] Connected to Google AI ({MODEL_NAME})")
            except Exception as e:
                print(f"   ⚠️ [System] Init Failed: {e}")
                self.is_cloud_alive = False

    def _save_usage(self, data):
        """Writes the usage data to the shared log file."""
        try:
            with open(USAGE_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f" ⚠️ [System] Failed to save usage log: {e}")

    def _load_usage(self):
        today_str = datetime.date.today().isoformat()
        # Initializing with token-based tracking
        default_data = {"date": today_str, "total_tokens": 0}

        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if not USAGE_FILE.exists():
            self._save_usage(default_data)
            return default_data

        try:
            with open(USAGE_FILE, 'r') as f:
                data = json.load(f)
            if data.get("date") != today_str:
                self._save_usage(default_data)
                return default_data
            return data
        except:
            return default_data

    def _update_token_usage(self, tokens):
        with self.lock: # Prevents race conditions during high RPM
            self.usage['total_tokens'] += tokens
            self._save_usage(self.usage)

    def think(self, prompt_text, is_local_run = False):
        if self.usage['total_tokens'] >= TOKEN_LIMIT:
            print(f"   🛑 [System] Token Limit Reached ({TOKEN_LIMIT}). Switching to Local Backup.")
            return self.backup.think(prompt_text)

        if not self.is_cloud_alive or is_local_run:
            return self.backup.think(prompt_text)

        for attempt in range(2):

            time.sleep(random.uniform(0.5, 2.0))
            try:
                # 2. DISPATCH: Use google-genai for strictly formatted JSON
                # print(f" 🤖 [System] Dispatching Request...")
                response = self.client.models.generate_content(
                    model=MODEL_NAME,
                    contents=f"{prompt_text}\n\nRETURN JSON ONLY.",
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )

                # 3. METRICS: Extract exact token usage from response metadata
                usage = response.usage_metadata
                actual_tokens = usage.prompt_token_count + usage.candidates_token_count
                
                # 4. LOGGING: Thread-safe update
                self._update_token_usage(actual_tokens)

                return json.loads(response.text)

            except Exception as e:
                print(f" ⚠️ [Engine] Cloud Attempt {attempt + 1} failed: {str(e)}...")
                time.sleep(10)

        print(f" ❌ [Engine] Cloud exhausted. Switching to Local Backup.")
        return self.backup.think(prompt_text)

    def see(self, image_path, prompt):
        if not self.is_cloud_alive:
            print("⚠️ Cloud disabled. Vision request skipped.")
            return None

        """Multimodal Vision capability for image-based resumes."""
        if self.usage['total_tokens'] >= TOKEN_LIMIT:
            print("🛑 Budget Exceeded. Vision rescue aborted.")
            return None

        from PIL import Image
        pil_image = Image.open(image_path)

        for attempt in range(1):
            
            time.sleep(random.uniform(0.5, 2.0))
            try:
                print(f" 🤖 [System] Dispatching Request... (VLM)")
                # Using the new google-genai SDK logic
                response = self.client.models.generate_content(
                    model=VLM_NAME,
                    contents=[prompt, pil_image],
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                
                # Log tokens using your existing thread-safe method
                usage = response.usage_metadata
                total = usage.prompt_token_count + usage.candidates_token_count
                self._update_token_usage(total)
                
                return json.loads(response.text)
            except Exception as e:
                print(f" ⚠️ [Engine] Cloud Attempt {attempt + 1} failed: {str(e)}...")
                time.sleep(10)
        
        print(f" ❌ [Engine] Cloud exhausted.")
        return None

# Testing
if __name__ == "__main__":
    # This block only runs if you execute this specific file
    engine = Engine()
    
    prompt = """
    Extract these details from this text:
    "My name is John Doe, a Python Developer with 5 years of experience."
    JSON Keys: name, role, years
    """
    print(f"Current Count: {engine.usage['total_tokens']}")
    
    result = engine.think(prompt)
    print("\n--------- RESULT ---------")
    print(json.dumps(result, indent=2))
    print(f"New Count: {engine.usage['total_tokens']}")
