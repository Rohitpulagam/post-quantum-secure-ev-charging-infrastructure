#!/bin/bash

# Quick Launch Script for Streamlit Web Interface
# ISO 15118 + PQC EV Charging System

echo "=========================================="
echo "ISO 15118 + PQC Web Interface Launcher"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "niso" ]; then
    echo "❌ Error: Virtual environment 'niso' not found!"
    echo "Please run setup first."
    exit 1
fi

# Activate virtual environment
echo "✓ Activating Python environment..."
source niso/bin/activate

# Check if streamlit is installed
if ! python -c "import streamlit" 2>/dev/null; then
    echo "⚠️  Streamlit not found. Installing..."
    pip install streamlit
fi

echo "✓ Starting Streamlit web interface..."
echo ""
echo "🌐 The interface will open automatically in your browser."
echo "📍 Local URL: http://localhost:8501"
echo "📍 Network URL: http://$(hostname -I | awk '{print $1}'):8501"
echo ""
echo "💡 To stop: Press Ctrl+C in this terminal"
echo ""
echo "=========================================="
echo ""

# Launch Streamlit
streamlit run streamlit_app.py
