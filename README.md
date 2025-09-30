# Demand Genius Chat API

Natural language content intelligence API with contextual query parsing and strategic advisory capabilities.

---

## 🚀 Tech Stack
- **Framework:** FastAPI `0.115.4`  
- **Language:** Python `3.11+`  
- **Database:** MongoDB `7.0+`  
- **Vector Storage:** PostgreSQL `15+` with `pgvector` (for semantic search)  
- **AI:** OpenAI Chat Completion models  
- **Auth:** JWT  

---

## 📋 Prerequisites
- Python `3.11` or higher  
- MongoDB `7.0+`  
- PostgreSQL `15+` with `pgvector` extension enabled   

---

## ⚙️ Installation

### 1. Clone the repository
```bash
git clone https://github.com/palakvanpariya-png/Demand_Genius_Chat_API.git
cd Demand_Genius_Chat_API

# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python -m venv venv
source venv/bin/activate

pip install -r requirements.txt
```
### Development

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
