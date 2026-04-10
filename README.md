# 🧠 PSM (Product Sales Management) AI System

A full-stack **Sales & Procurement Management System** powered by **FastAPI**, **PostgreSQL**, and a **LangGraph-based AI Agent** using local LLMs (Ollama).  
The system integrates traditional backend architecture with a **RAG-based intelligent assistant** for automation and decision support.

---

## 🚀 Overview

PSM is a backend-driven application that supports:

- User authentication & role-based access
- Product inventory management
- Sales tracking & history
- Analytics & reporting
- AI-powered chatbot with real-time business context

---

## 🧩 Architecture
Frontend (HTML/JS)
↓
FastAPI Backend
↓
LangGraph AI Agent
↓
RAG (FAISS Vector DB)
↓
Ollama Local LLM
↓
PostgreSQL Database

---

## 📁 Project Structure
psm/
├── app/                        # Main Application Codebase
│   ├── routers/                # API Route Handlers
│   │   ├── analytics.py        # Analytics and store statistics endpoints
│   │   ├── auth.py             # User authentication, mapping to auth table
│   │   ├── chatbot.py          # Chatbot interactive endpoints
│   │   ├── products.py         # CRUD for products inventory
│   │   ├── reports.py          # Auto-generating reports (e.g., FPDF based)
│   │   └── sales.py            # Sales operations and history endpoints
│   ├── services/               # Core business logic & AI orchestration
│   │   └── agent_service.py    # LangGraph & LangChain agent logic, FAISS integrations
│   ├── crud.py                 # Core Database interactions (Create, Read, Update, Delete)
│   ├── database.py             # SQLAlchemy configuration and database connection
│   ├── models.py               # Database schemas / ORM definitions
│   └── schemas.py              # Pydantic schemas for data validation
├── impleM/                     # Implementation notes and scratchpad directory (Git-ignored)
├── __pycache__/                # Python cache
├── .faiss_index/               # Local vector storage for chatbot RAG operations
├── .gitignore                  # Definitions for untracked files
├── add_users.py                # Setup utility to seed user accounts
├── dashboard.html              # Frontend user interface dashboard
├── login.html                  # Frontend user login interface
├── register.html               # Frontend user registration interface
├── main.py                     # Entry point for backend server
└── requirements.txt            # Project dependencies


---

## 🔐 Role-Based Features

### 👤 Customer
- Browse products
- Add/remove items from cart
- Purchase products
- View personal order history

### 📦 Supplier
- Manage own products
- Update stock and pricing
- View inventory and sales

### 🛠️ Admin
- Full system control
- Manage all products
- Procurement from suppliers
- View analytics (revenue, top products, stock alerts)

---

## 🤖 AI Agent (LangGraph-Based)

- Stateful conversational agent
- Multi-step workflow:
  - Intent → Preview → Confirm → Execute
- Uses **RAG (FAISS)** for real-time data retrieval
- Runs on **local LLM (Ollama)**

---

## 🧠 RAG (Retrieval-Augmented Generation)

- Product & sales data embedded into FAISS
- Context retrieved dynamically per query
- Auto-sync after every DB update
- Ensures accurate, non-hallucinated responses

---

## ⚙️ Tech Stack

- **Backend:** FastAPI, Uvicorn  
- **Database:** PostgreSQL, SQLAlchemy  
- **AI Framework:** LangChain, LangGraph  
- **LLM Runtime:** Ollama (Local Models)  
- **Vector DB:** FAISS  
- **Frontend:** HTML, CSS, JavaScript  
- **Reports:** FPDF  

