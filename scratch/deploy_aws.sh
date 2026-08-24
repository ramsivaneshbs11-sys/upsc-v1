#!/bin/bash
# ==============================================================================
# deploy_aws.sh
# 
# Automated deployment script for UPSC RAG FastAPI application on AWS EC2 (Ubuntu).
# Run this inside the EC2 instance.
# ==============================================================================

set -e # Exit immediately on error

echo "=== 1. Updating System Packages ==="
sudo apt update -y
sudo apt upgrade -y

echo "=== 2. Installing Python & Git ==="
sudo apt install python3 python3-pip python3-venv git curl -y

# Verify installations
python3 --version
pip3 --version
git --version

echo "=== 3. Cloning Repository ==="
# User should replace this with their actual GitHub repository URL
REPO_URL="https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git"
PROJECT_DIR="RAG-main"

if [ -d "$PROJECT_DIR" ]; then
    echo "Directory $PROJECT_DIR already exists. Pulling latest changes..."
    cd "$PROJECT_DIR"
    git pull
else
    echo "Cloning repository: $REPO_URL..."
    # If repository is private, user might need to authenticate
    git clone "$REPO_URL" "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

echo "=== 4. Setting up Python Virtual Environment ==="
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip

echo "=== 5. Installing Dependencies ==="
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "WARNING: requirements.txt not found!"
fi

echo "=== 6. Creating Environment Variables File (.env) ==="
if [ ! -f ".env" ]; then
    echo "Creating a new .env file. Please make sure to fill in your API keys!"
    cat <<EOT >> .env
# PostgreSQL connection string (Update with your VM or RDS postgres server)
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/upsc_rag

# Qdrant vector database (Update with Qdrant Cloud or local VM address)
QDRANT_HOST=localhost
QDRANT_PORT=6333

# Embedding and Reranker models
EMBEDDING_MODEL_NAME=BAAI/bge-base-en-v1.5
RERANKER_MODEL_NAME=cross-encoder/ms-marco-MiniLM-L-6-v2
RETRIEVAL_CANDIDATE_K=10

# API Keys (Update these with actual keys)
GEMINI_API_KEY=YOUR_GEMINI_API_KEY
GROQ_API_KEY=YOUR_GROQ_API_KEY
GROQ_MODEL=openai/gpt-oss-120b
EOT
    echo ".env template created successfully."
else
    echo ".env file already exists. Skipping creation."
fi

echo "=== 7. Instructions to run the application ==="
echo "------------------------------------------------------------"
echo "Deployment setup is complete! To start the FastAPI server:"
echo "1. Activate virtualenv: source venv/bin/activate"
echo "2. Edit .env with your real API keys: nano .env"
echo "3. Run FastAPI using Uvicorn (exposed on port 8000):"
echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo "------------------------------------------------------------"
