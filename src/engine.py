import time
import json
import requests
from src.backup_engine import LocalEngine # ✅ NEW: Import the safety net

# --- ENGINE CONFIGURATION ---
API_KEY = "" # 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
MODEL_NAME = "nvidia/nemotron-3-nano-30b-a3b:free"

class Engine:
    def __init__(self):
        self.api_key = API_KEY
        self.model_name = MODEL_NAME
        self.url = "https://openrouter.ai/api/v1/chat/completions"
        self.key_url = "https://openrouter.ai/api/v1/auth/key" # ✅ NEW: Fuel Gauge Endpoint
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/AgencyControl",
            "X-Title": "AgencyControl"
        }
        self.backup = LocalEngine() # ✅ NEW: Initialize backup

        # 🔍 RUN DIAGNOSTIC ON STARTUP
        # This checks your fuel (credits) immediately when the program starts.
        self.is_cloud_alive = self.check_fuel()

    def check_fuel(self):
        """
        Checks if the API Key is valid and has credits.
        Returns True if Cloud is ready, False if we should use Backup.
        """
        print("   🔍 [System] Checking Cloud Fuel Gauge...")
        
        # If no key is provided, fail immediately to Backup
        if not self.api_key or len(self.api_key) < 10:
            print("   ⚠️ [System] No API Key found. Disabling Cloud.")
            return False

        try:
            response = requests.get(self.key_url, headers=self.headers, timeout=5)
            
            if response.status_code == 200:
                data = response.json().get('data', {})
                limit = data.get('limit')
                usage = data.get('usage')
                
                # Logic: If limit exists and usage >= limit, you are out of credits.
                # (If limit is None, it usually means unlimited/free tier, which is good).
                if limit is not None and usage is not None:
                    remaining = limit - usage
                    if remaining <= 0:
                        print("   ❌ [System] Cloud Out of Credits. Disabling Cloud.")
                        return False
                
                print("   ✅ [System] Cloud Connection: ACTIVE")
                return True
            else:
                print(f"   ⚠️ [System] Cloud Auth Failed ({response.status_code}). Disabling Cloud.")
                return False
        except Exception as e:
            print(f"   ⚠️ [System] Cloud Unreachable ({e}). Disabling Cloud.")
            return False

    def think(self, prompt_text: str, retries: int = 0) -> dict:
        # ✅ NEW: STEERING LOGIC
        # If we already know the cloud is dead/empty, don't waste time waiting 7s.
        # Go straight to local backup.
        if not self.is_cloud_alive:
            return self.backup.think(prompt_text)

        MAX_RETRIES = 2 # Reduced slightly so it switches to backup faster
        
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a precise JSON-only extraction engine. You do not speak markdown. You only output valid JSON."},
                {"role": "user", "content": prompt_text + "\n\nRETURN ONLY RAW JSON."}
            ],
            "reasoning": {"enabled": True},
            "response_format": {"type": "json_object"}
        }

        try:
            time.sleep(7)  # Preserving your pacing to avoid rate limits
            
            response = requests.post(
                self.url, 
                headers=self.headers, 
                data=json.dumps(payload),
                timeout=45 
            )

            # Error Handling
            if response.status_code != 200:
                if response.status_code == 429:
                    if retries >= MAX_RETRIES:
                        print(f"   ❌ [Engine] Max Retries Hit. Switching to Backup...")
                        return self.backup.think(prompt_text) # ✅ Failover!
                    
                    wait_time = 10 * (retries + 1)
                    print(f"   ⏳ [Engine] Rate Limit (429). Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                    return self.think(prompt_text, retries + 1)
                
                print(f"   ⚠️ [Engine] API Error {response.status_code}. Switching to Backup...")
                return self.backup.think(prompt_text) # ✅ Failover!

            # Parsing
            data = response.json()
            content = data['choices'][0]['message']['content']
            
            # --- ROBUST CLEANER ---
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
            
            # Find the first '{' and last '}' just in case there is chatty text
            start = content.find('{')
            end = content.rfind('}')
            if start != -1 and end != -1:
                content = content[start:end+1]
            # ----------------------
                
            return json.loads(content)

        except Exception as e:
            print(f"   ⚠️ [Engine] Connection Error: {e}. Switching to Backup...")
            return self.backup.think(prompt_text) # ✅ Failover!

if __name__ == "__main__":
    print("\n🧪 STARTING HYBRID ENGINE DIAGNOSTICS...")
    engine = Engine()
    print(f"   Primary: {MODEL_NAME}")
    print(f"   Backup:  Llama 3 (Local)")
    
    res = engine.think("Return JSON: { 'status': 'online' }")
    if res: print(f"✅ SUCCESS: {res}")
    else: print("❌ FAILURE")