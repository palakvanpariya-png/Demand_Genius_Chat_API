# Demand Genius Chat API
Natural language content intelligence API with contextual query parsing and strategic advisory capabilities.

## Tech Stack

Framework: FastAPI 0.115.4
Language: Python 3.11+
Database: MongoDB 7.0+
Vector Storage: PostgreSQL 15+ with pgvector (for semantic search)
AI: OpenAI Chat Completion models
Auth: JWT

## Prerequisites

Python 3.11 or higher
MongoDB 7.0+
PostgreSQL 15+ with pgvector extension
OpenAI API key (GPT-4o access)

Installation

Clone the repository:

bashgit clone https://github.com/palakvanpariya-png/Demand_Genius_Chat_API.git
cd Demand_Genius_Chat_API

Create virtual environment:

bashpython -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux

Install dependencies:

bashpip install -r requirements.txt

Setup PostgreSQL pgvector:

sqlCREATE EXTENSION vector;

Create .env file:

env# MongoDB
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
DATABASE_NAME=database_name


# OpenAI
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o
OPENAI_TEMPERATURE=0.0

# API
API_HOST=0.0.0.0
API_PORT=8000
DEBUG=False

# JWT
JWT_SECRET_KEY=your_jwt_secret_key_here
JWT_ALGORITHM=HS256
Running the Application

# Development:
bashuvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production:
bashuvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4