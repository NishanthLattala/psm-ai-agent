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
<img width="784" height="630" alt="image" src="https://github.com/user-attachments/assets/8358cee5-e7ca-4910-9915-5e0b5cd1a386" />



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

