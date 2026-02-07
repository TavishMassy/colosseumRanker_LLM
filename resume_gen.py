import os
import random
import json
import string
from pathlib import Path

# --- CONFIG ---
RAW_DATA_DIR = Path("data/resumes")
RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Real-ish links to test the Scraper
REAL_PORTFOLIOS = [
    "https://brittanychiang.com/",
    "https://bruno-simon.com/", 
    "https://matthewfarley.ca/",
    "https://tamalsen.dev/",
    "https://www.jenniferdewalt.com/",
    "https://leerob.io/",
    "https://overreacted.io/",
    "https://github.com/torvalds",
    "https://stackoverflow.com/users/1",
    "https://news.ycombinator.com/"
]

FAKE_BLOGS = [
    "https://medium.com/@fake_dev_123/how-i-learned-react-in-1-day",
    "https://dev.to/wannabe_coder/why-html-is-a-programming-language",
    "https://zapier.com/blog/case-study-examples/", # The Trap Link
    "http://localhost:3000", # Broken Link
    "https://linkedin.com/in/fake-profile-999" # Social Link (Should be skipped by Scraper)
]

SKILL_SETS = {
    "Web": ["React", "Node.js", "TypeScript", "Next.js", "Tailwind", "GraphQL", "PostgreSQL"],
    "Systems": ["Rust", "C++", "Go", "Linux", "Kernel", "Embedded", "Assembly"],
    "AI": ["Python", "PyTorch", "TensorFlow", "CUDA", "LLM", "RAG", "LangChain"],
    "Buzzword": ["Synergy", "Blockchain", "Web3", "Metaverse", "NFT", "Growth Hacking", "Disruption"]
}

def get_random_contact(name):
    domain = random.choice(["gmail.com", "outlook.com", "protonmail.com", "dev-hub.io", "tech-corp.net"])
    clean_name = name.lower().replace(" ", ".")
    email = f"{clean_name}.{random.randint(10, 99)}@{domain}"
    phone = f"+{random.randint(1, 99)} {random.randint(200, 999)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}"
    return email, phone

def generate_bio(role, years, skills):
    intros = [
        f"Highly motivated {role} with {years} years of experience.",
        f"Passionate {role} specializing in scalable architecture.",
        f"Results-driven professional with a track record in {skills[0]} and {skills[1]}.",
        f"I am a {role} who loves building things that break things.",
        f"Visionary leader transforming the {role} landscape."
    ]
    
    body = [
        f"Successfully led a team of {random.randint(3, 15)} engineers to deploy critical infrastructure.",
        f"Reduced latency by {random.randint(10, 80)}% using advanced {skills[random.randint(0, len(skills)-1)]} techniques.",
        f"Managed a budget of ${random.randint(50, 500)}k for cloud migration projects.",
        f"Authored multiple libraries in {skills[1]} downloaded over {random.randint(1000, 1000000)} times.",
        f"Speaker at {random.choice(['PyCon', 'ReactConf', 'KubeCon', 'Local Meetup'])} 2024.",
        f"Implemented a {skills[2]} pipeline that saved the company {random.randint(100, 500)} hours annually."
    ]
    
    return f"{random.choice(intros)}\n\nPROFESSIONAL SUMMARY:\n" + "\n".join(random.sample(body, 3))

def generate_sophisticated_chaos():
    resumes = []
    
    # 1. THE "PERFECT" CANDIDATES (Top 5 - High Skill, Good Links)
    for i in range(5):
        name = f"Alpha Candidate {i}"
        email, phone = get_random_contact(name)
        skills = SKILL_SETS["Systems"] + SKILL_SETS["AI"]
        links = random.sample(REAL_PORTFOLIOS, 2)
        
        content = f"""
        NAME: {name}
        CONTACT: {email} | {phone}
        ROLE: Senior Systems Architect
        LINKS: {', '.join(links)}
        
        {generate_bio('Systems Architect', random.randint(8, 15), skills)}
        
        TECHNICAL ARSENAL: {', '.join(skills)}
        
        EXPERIENCE:
        - Principal Engineer at TechCorp (2018-Present): Led the migration from monolith to microservices using {skills[0]}.
        - Senior Dev at StartupX (2014-2018): Scaled user base to 1M+ using {skills[1]} and {skills[2]}.
        """
        resumes.append({"type": "Alpha", "name": name.replace(" ", "_"), "content": content})

    # 2. THE "BUZZWORD" BOTS (Top 10 - High Keyword Density, Trash Links)
    for i in range(10):
        name = f"Buzzword Bot {i}"
        email, phone = get_random_contact(name)
        skills = SKILL_SETS["Buzzword"] + SKILL_SETS["Web"]
        links = [random.choice(FAKE_BLOGS), "https://zapier.com/blog/case-study-examples/"]
        
        content = f"""
        NAME: {name}
        CONTACT: {email} | {phone}
        ROLE: Visionary Tech Ninja
        LINKS: {', '.join(links)}
        
        SUMMARY:
        I leverage synergistic paradigms to disrupt the blockchain metaverse. utilizing {skills[0]} and {skills[1]} to drive growth hacking KPIs.
        
        SKILLS: {', '.join(skills)}
        
        EXPERIENCE:
        - CEO of Self (2020-Present): Thought leadership in {skills[2]}.
        - Consultant (2019-2020): Ideated NFT solutions for {skills[3]}.
        """
        resumes.append({"type": "Bot", "name": name.replace(" ", "_"), "content": content})

    # 3. THE "JUNIOR" DEVS (Top 15 - Good intent, Low Exp, Mixed Links)
    for i in range(15):
        name = f"Junior Dev {i}"
        email, phone = get_random_contact(name)
        skills = SKILL_SETS["Web"]
        links = [random.choice(REAL_PORTFOLIOS)]
        
        content = f"""
        NAME: {name}
        PHONE: {phone}
        EMAIL: {email}
        ROLE: Junior Web Developer
        PORTFOLIO: {links[0]}
        
        OBJECTIVE: Eager to learn and grow as a {skills[0]} developer.
        
        PROJECTS:
        - ToDo App: Built with {skills[1]} and {skills[2]}.
        - Weather App: Used {skills[3]} API.
        
        EDUCATION:
        - Bootcamp Grad 2023
        """
        resumes.append({"type": "Junior", "name": name.replace(" ", "_"), "content": content})

    # 4. THE "DATA POISON" (Top 5 - Valid Text, Wrong Role)
    for i in range(5):
        name = f"Chef Gordon {i}"
        email, phone = get_random_contact(name)
        links = ["https://www.foodnetwork.com/"]
        
        content = f"""
        NAME: {name}
        CONTACT: {email}
        PHONE: {phone}
        ROLE: Executive Chef
        WEBSITE: {links[0]}
        
        SUMMARY:
        Expert in French Cuisine and Kitchen Management. I handle high-pressure environments (Dinner Service).
        Looking to pivot to Tech because I heard it pays well.
        
        SKILLS: Knife Skills, Sauce Making, Inventory Management, HACCP.
        """
        resumes.append({"type": "Noise", "name": name.replace(" ", "_"), "content": content})

    # 5. THE "GHOSTS" (Top 5 - No Contact Info, Great Skills)
    for i in range(5):
        name = f"Ghost Protocol {i}"
        skills = SKILL_SETS["Systems"]
        
        content = f"""
        NAME: {name}
        ROLE: Elite Hacker
        
        {generate_bio('Security Researcher', 10, skills)}
        
        SKILLS: {', '.join(skills)}
        NOTE: I do not provide contact info. Find me if you can.
        """
        resumes.append({"type": "Ghost", "name": name.replace(" ", "_"), "content": content})

    # 6. THE "BROKEN" FILES (Top 10 - Malformed Format)
    for i in range(10):
        name = f"Glitch User {i}"
        email, phone = get_random_contact(name)
        
        content = f"""
        Name:{name}Email:{email}Phone:{phone}
        
        Experience:2010-2015 worked at google doing java 2015-2020 worked at facebook doing python
        skills:java python c++
        
        links: http://broken-link.com
        """
        resumes.append({"type": "Broken", "name": name.replace(" ", "_"), "content": content})

    return resumes

def run():
    print("🧹 Cleaning old resumes...")
    for f in RAW_DATA_DIR.glob("*.txt"):
        f.unlink()
        
    all_data = generate_sophisticated_chaos()
    print(f"🚀 Deploying {len(all_data)} Heavy-Duty Resumes to {RAW_DATA_DIR}...")
    
    for i, entry in enumerate(all_data):
        filename = RAW_DATA_DIR / f"{entry['type']}_{i:03d}_{entry['name']}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(entry['content'])
            
    print(f"✅ Created {len(all_data)} files.")
    print("📊 Distribution:")
    print("   - Alpha (Perfect): 5")
    print("   - Bot (Buzzwords): 10")
    print("   - Junior (Weak): 15")
    print("   - Noise (Wrong Role): 5")
    print("   - Ghost (No Contact): 5")
    print("   - Broken (Bad Format): 10")
    print("\n🚦 Ready for Phase 1 (Extractor).")

if __name__ == "__main__":
    run()