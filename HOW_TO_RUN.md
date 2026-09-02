# 🚀 UPSC Chatbot Execution Guide

This document provides clear instructions on how to set up and run the UPSC Chatbot application, including the Frontend, Backend, and Automated News Pipeline.

---

## 🛠️ Prerequisites

Before starting, ensure you have the following installed on your system:

1.  **Node.js** (v18 or higher) - [Download](https://nodejs.org/)
2.  **Python** (v3.10 or higher) - [Download](https://www.python.org/)
3.  **MongoDB** (Running locally on `mongodb://localhost:27017`)
4.  **Git** (Optional, for version control)

---

## ⚡ The Quickest Way (Windows Only)

We have provided a unified startup script that handles everything for you.

1.  Open the project folder in your terminal or file explorer.
2.  Run the following command:
    ```powershell
    .\start_dev.bat
    ```
    *This will:*
    * Clear any existing processes on ports 8000 and 5173.
    * Start the **Backend API** (FastAPI) with hot-reload.
    * Start the **Frontend** (Vite) development server.
    * Open the application in your default browser automatically.

---

## 🧪 Manual Setup (Step-by-Step)

If you prefer to run services manually or are on a different OS, follow these steps:

### 1. Environment Configuration
Ensure your `.env` file in the root directory contains the necessary API keys:
```env
OPENAI_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here
MONGODB_URI=mongodb://localhost:27017
```

### 2. Backend Setup
1. Open a terminal in the root directory.
2. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the FastAPI server:
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```
   *The backend will be available at: `http://localhost:8000` (Swagger docs at `http://localhost:8000/docs`)*


### 3. Frontend Setup
1. Open a **new** terminal in the root directory.
2. Navigate to the frontend folder:
   ```bash
   cd frontend
   ```
3. Install dependencies:
   ```bash
   npm install
   ```
4. Start the development server:
   ```bash
   npm run dev
   ```
   *The frontend will be available at: `http://localhost:5173`*

---

## 📰 News Pipeline (Automation)

The news scraper is integrated into the backend but can be run independently for testing:

```bash
python pipeline/daily_news_pipeline.js
```
*Note: The pipeline is scheduled to run automatically twice a day (08:00 AM and 08:00 PM) when the backend is active.*

---

## 🔧 Troubleshooting

- **Port Conflict:** If you see "Address already in use", run `start_dev.bat` as it automatically clears ports 8000 and 5173.
- **MongoDB Error:** Ensure MongoDB Compass or the MongoDB service is running on your machine.
- **Missing Dependencies:** Run `npm install` inside the `frontend` folder and `pip install -r requirements.txt` in the root if you see "Module not found" errors.

---
*Developed by Crack-Developers*
