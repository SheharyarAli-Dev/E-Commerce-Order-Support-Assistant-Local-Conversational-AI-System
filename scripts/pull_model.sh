#!/usr/bin/env bash
# scripts/pull_model.sh
# Pull the required quantized LLM model via Ollama.
#
# Usage:
#   chmod +x scripts/pull_model.sh
#   ./scripts/pull_model.sh

set -e

MODEL="qwen2.5:1.5b"

echo "=============================================="
echo "  ShopBot — Model Setup"
echo "=============================================="
echo ""
echo "Checking if Ollama is installed..."
if ! command -v ollama &> /dev/null; then
    echo "ERROR: Ollama is not installed."
    echo "Please install it from: https://ollama.com/download"
    exit 1
fi

echo "Ollama found: $(ollama --version)"
echo ""
echo "Starting Ollama server (if not already running)..."
ollama serve &>/dev/null &
sleep 2

echo "Pulling model: $MODEL"
echo "This may take a few minutes (~1 GB download)..."
echo ""
ollama pull "$MODEL"

echo ""
echo "✓ Model '$MODEL' is ready."
echo ""
echo "To start ShopBot:"
echo "  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
