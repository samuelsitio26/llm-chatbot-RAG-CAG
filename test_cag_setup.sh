#!/bin/bash

# Test script for CAG implementation
# Run this to verify everything is working

echo "================================================"
echo "🧪 CAG System Implementation Test"
echo "================================================"
echo ""

# Check conda environment
echo "1. Checking conda environment..."
if conda env list | grep -q "llm-rag"; then
    echo "   ✅ llm-rag environment found"
else
    echo "   ❌ llm-rag environment NOT found"
    echo "   Create it with: conda create -n llm-rag python=3.10"
    exit 1
fi
echo ""

# Check project structure
echo "2. Checking project structure..."
if [ -d "database/kv_cache" ] && [ -d "database/summary_cache" ]; then
    echo "   ✅ Database folders exist"
else
    echo "   ❌ Database folders missing"
    exit 1
fi

if [ -d "data/tourism" ]; then
    echo "   ✅ Tourism data folder exists"
else
    echo "   ❌ Tourism data folder missing"
    exit 1
fi
echo ""

# Check Python files
echo "3. Checking CAG Python files..."
required_files=(
    "src/__init__.py"
    "src/app_cag.py"
    "src/cag_system.py"
    "src/kv_cache_manager.py"
    "src/summary_cache.py"
)

for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo "   ✅ $file"
    else
        echo "   ❌ $file missing"
        exit 1
    fi
done
echo ""

# Check PDF dataset
echo "4. Checking tourism PDF dataset..."
pdf_count=$(find data/tourism -name "*.pdf" 2>/dev/null | wc -l)
echo "   📄 Found $pdf_count PDF file(s)"

if [ $pdf_count -eq 0 ]; then
    echo "   ⚠️  No PDFs found. Add your 9 tourism PDFs to data/tourism/"
elif [ $pdf_count -lt 9 ]; then
    echo "   💡 You have $pdf_count PDFs. Consider adding $((9 - pdf_count)) more."
elif [ $pdf_count -eq 9 ]; then
    echo "   🎯 Perfect! You have 9 PDFs as recommended."
else
    echo "   ✨ Great! You have $pdf_count PDFs for extensive coverage."
fi
echo ""

# Check dependencies
echo "5. Checking Python dependencies..."
source activate llm-rag 2>/dev/null || conda activate llm-rag

if python -c "import streamlit" 2>/dev/null; then
    echo "   ✅ streamlit"
else
    echo "   ❌ streamlit missing - run: pip install -r requirements.txt"
fi

if python -c "import torch" 2>/dev/null; then
    echo "   ✅ torch"
else
    echo "   ❌ torch missing"
fi

if python -c "import transformers" 2>/dev/null; then
    echo "   ✅ transformers"
else
    echo "   ❌ transformers missing"
fi
echo ""

# GPU Check
echo "6. Checking GPU availability..."
if command -v nvidia-smi &> /dev/null; then
    gpu_info=$(nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1)
    echo "   ✅ GPU: $gpu_info"
else
    echo "   ⚠️  nvidia-smi not found (GPU may not be available)"
fi
echo ""

# Summary
echo "================================================"
echo "✅ CAG Implementation Test Complete!"
echo "================================================"
echo ""
echo "🚀 Next steps:"
echo ""
echo "1. Add your 9 tourism PDFs to: data/tourism/"
echo "2. Validate dataset: python data/prepare_dataset.py"
echo "3. Run CAG chatbot: streamlit run src/app_cag.py"
echo "4. Access at: http://172.22.222.118:8501"
echo ""
echo "📖 Documentation:"
echo "   - Quick Start: QUICKSTART_CAG.md"
echo "   - Full Summary: CAG_IMPLEMENTATION_SUMMARY.md"
echo ""
