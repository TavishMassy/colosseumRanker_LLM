import os
import random
from pathlib import Path

# --- CONFIG ---
RAW_DATA_DIR = Path("data/resumes")
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Test Data Pools
REAL_PORTFOLIOS = ["https://github.com/torvalds", "https://leerob.io", "https://bruno-simon.com"]
CITIES = ["Jaipur", "Bangalore", "Mumbai", "Remote", "New York", "London"]
COMPANIES = {
    "Product": ["Google", "Uber", "Zomato", "Cred", "Stripe"],
    "Service": ["TCS", "Infosys", "Wipro", "Accenture", "Cognizant"]
}

def get_contact(name):
    clean = name.lower().replace(" ", ".")
    return f"{clean}@{random.choice(['gmail.com', 'outlook.com'])}", f"+91-98{random.randint(10000000, 99999999)}"

def generate_sophisticated_chaos():
    resumes = []
    
    # 1. THE "UNICORN" (Alpha) - Immediate Joiner, Product Co, Right Location
    # EXPECTATION: Rank #1, Low Risk, Notice: "Immediate"
    for i in range(5):
        name = f"Alpha Candidate {i}"
        email, phone = get_contact(name)
        skills = "Rust, Go, Kubernetes, AWS, Kafka, Microservices"
        
        content = f"""
        NAME: {name}
        LOCATION: Jaipur, India
        CONTACT: {email} | {phone}
        LINKS: {random.choice(REAL_PORTFOLIOS)}
        
        SUMMARY:
        Staff Engineer at {random.choice(COMPANIES['Product'])} handling 1M+ RPS.
        Currently serving notice period (Last working day: Next Friday).
        
        EXPERIENCE:
        - Staff Engineer @ {random.choice(COMPANIES['Product'])} (2020-Present): Scaled payments engine.
        - Senior Dev @ Swiggy (2016-2020): Built logistics layer.
        
        NOTICE PERIOD: Serving Notice (10 Days remaining).
        SKILLS: {skills}
        """
        resumes.append({"type": "Alpha", "name": name.replace(" ", "_"), "content": content})

    # 2. THE "CORPORATE TRAP" - Good Skills, but 90 Day Notice
    # EXPECTATION: Good Rank, but Flagged for "90 Days Notice"
    for i in range(5):
        name = f"Corporate Dev {i}"
        email, phone = get_contact(name)
        company = random.choice(COMPANIES['Service'])
        
        content = f"""
        NAME: {name}
        LOCATION: Bangalore
        CONTACT: {email} | {phone}
        
        SUMMARY:
        Team Lead at {company} with 8 years of Java/Springboot experience.
        Expert in banking domains.
        
        EXPERIENCE:
        - Team Lead @ {company} (2018-Present): Managing 20 devs.
        
        NOTICE PERIOD: 3 Months (Negotiable).
        SKILLS: Java, Spring Boot, Oracle, Jenkins, SOAP API.
        """
        resumes.append({"type": "Trap", "name": name.replace(" ", "_"), "content": content})

    # 3. THE "JOB HOPPER" - Great Skills, but leaves every 6 months
    # EXPECTATION: High Risk Audit -> "Job Hopper" flag
    for i in range(5):
        name = f"Hopper {i}"
        email, phone = get_contact(name)
        
        content = f"""
        NAME: {name}
        CONTACT: {email} | {phone}
        
        SUMMARY:
        Fast-paced developer looking for new challenges.
        
        EXPERIENCE:
        - Dev @ Startup A (Jan 2024 - Present)
        - Dev @ Crypto B (June 2023 - Dec 2023)
        - Dev @ AI Corp (Jan 2023 - May 2023)
        - Intern @ Web Shop (Aug 2022 - Dec 2022)
        
        SKILLS: React, Node.js, Web3, Solidity.
        NOTICE: Immediate.
        """
        resumes.append({"type": "Hopper", "name": name.replace(" ", "_"), "content": content})

    # 4. THE "GHOST" (No Contact)
    # EXPECTATION: Filtered out by Auditor or Ghostbuster
    for i in range(3):
        name = f"Ghost Protocol {i}"
        content = f"""
        NAME: {name}
        ROLE: Senior Architect
        SKILLS: Python, AI, ML, Data Science.
        EXPERIENCE: 10 Years at Google.
        NOTE: Contact me on LinkedIn (Link not provided).
        """
        resumes.append({"type": "Ghost", "name": name.replace(" ", "_"), "content": content})

    # 5. THE "GLITCH" (Malformed)
    # EXPECTATION: Low Score or "Insufficient Data" verdict
    for i in range(3):
        name = f"Glitch User {i}"
        email, phone = get_contact(name)
        content = f"""
        Name:{name}Email:{email}Phone:{phone}
        Exp: java 2010-2023
        skills: java
        """
        resumes.append({"type": "Glitch", "name": name.replace(" ", "_"), "content": content})

    return resumes

def run():
    print("🧹 Cleaning old resumes...")
    for f in RAW_DATA_DIR.glob("*.txt"):
        f.unlink()
        
    all_data = generate_sophisticated_chaos()
    print(f"🚀 Deploying {len(all_data)} Recruitment Scenarios...")
    
    for i, entry in enumerate(all_data):
        filename = RAW_DATA_DIR / f"{entry['type']}_{i:03d}_{entry['name']}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(entry['content'])
            
    print(f"✅ Created {len(all_data)} files.")
    print("📊 Scenarios:")
    print("   - Alpha (Immediate/Product): 5")
    print("   - Trap (90 Day Notice): 5")
    print("   - Hopper (Frequent Switches): 5")
    print("   - Ghost (No Contact): 3")
    print("   - Glitch (Bad Format): 3")

if __name__ == "__main__":
    run()