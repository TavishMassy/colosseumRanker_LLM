import time
import json
import os
import sys
import datetime
from pathlib import Path
from google import genai
from google.genai import types

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.backup_engine import LocalEngine 

# --- ENGINE CONFIGURATION ---
API_KEY = ""
MODEL_NAME = "gemini-flash-latest"
DAILY_LIMIT = 1000
Requests_Per_Minute = 15  # Requests Per Minute
USAGE_FILE = Path("data/usage_log.json")
# ----------------------------

class Engine:
    def __init__(self):
        self.api_key = API_KEY
        self.backup = LocalEngine()
        self.is_cloud_alive = True

        self.usage = self._load_usage()
        print(f"   📊 [System] Daily Usage: {self.usage['count']}/{DAILY_LIMIT} (Date: {self.usage['date']})")

        if not self.api_key or "AIza" not in self.api_key:
            print("   ⚠️ [System] Invalid or Missing Google API Key. Disabling Cloud.")
            self.is_cloud_alive = False
        else:
            try:
                self.client = genai.Client(api_key=self.api_key)
                if self.is_cloud_alive:
                    print(f"   ✅ [System] Connected to Google AI ({MODEL_NAME})")
            except Exception as e:
                print(f"   ⚠️ [System] Init Failed: {e}")
                self.is_cloud_alive = False

    def _load_usage(self):
        """Reads the log file and resets it if the day has changed."""
        today_str = datetime.date.today().isoformat()
        default_data = {"date": today_str, "count": 0}

        # Ensure directory exists
        USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)

        if not USAGE_FILE.exists():
            self._save_usage(default_data)
            return default_data

        try:
            with open(USAGE_FILE, 'r') as f:
                data = json.load(f)
            
            # If dates don't match, it's a new day! Reset to 0.
            if data.get("date") != today_str:
                print("   🔄 [System] New Day Detected! Resetting Daily Counter.")
                self._save_usage(default_data)
                return default_data
            
            return data
        except:
            return default_data

    def _save_usage(self, data):
        with open(USAGE_FILE, 'w') as f:
            json.dump(data, f)

    def think(self, prompt_text: str) -> dict:
        if self.usage['count'] >= DAILY_LIMIT:
            if self.is_cloud_alive: # Only print this once per run ideally
                print(f"   🛑 [System] Daily Limit Reached ({DAILY_LIMIT}). Switching to Local Backup.")
                self.is_cloud_alive = False
            return self.backup.think(prompt_text)

        if not self.is_cloud_alive:
            return self.backup.think(prompt_text)

        try:
            time.sleep(60 / Requests_Per_Minute)  # Preserving pacing to avoid rate limits (15 RPM)
            
            response = self.client.models.generate_content(
                model=MODEL_NAME,
                contents=f"{prompt_text}\n\nRETURN JSON ONLY.",
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            self.usage['count'] += 1
            self._save_usage(self.usage)

            return json.loads(response.text)

        except Exception as e:
            # Catching generic errors as specific Google errors have changed locations
            print(f"   ⚠️ [Engine] Error: {e}. Switching to Backup.")
            self.is_cloud_alive = False
            return self.backup.think(prompt_text)

# Testing
if __name__ == "__main__":
    # This block only runs if you execute this specific file
    engine = Engine()
    
    prompt = """
    Extract these details from this text:
    "My name is John Doe, a Python Developer with 5 years of experience."
    JSON Keys: name, role, years
    """
    print(f"Current Count: {engine.usage['count']}")
    
    result = engine.think(prompt)
    print("\n--------- RESULT ---------")
    print(json.dumps(result, indent=2))
    print(f"New Count: {engine.usage['count']}")