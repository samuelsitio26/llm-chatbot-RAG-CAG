"""
Script to validate and prepare tourism dataset
"""

import os
import sys

TOURISM_FOLDER = os.path.join(os.path.dirname(__file__), "tourism")

def check_pdfs():
    """Check if PDFs are present and valid"""
    
    if not os.path.exists(TOURISM_FOLDER):
        print(f"❌ Tourism folder not found: {TOURISM_FOLDER}")
        return False
    
    pdf_files = [f for f in os.listdir(TOURISM_FOLDER) if f.endswith('.pdf')]
    
    print("=" * 60)
    print("📊 Tourism Dataset Validation")
    print("=" * 60)
    print(f"\n📁 Folder: {TOURISM_FOLDER}\n")
    
    if len(pdf_files) == 0:
        print("❌ No PDF files found!")
        print("\nPlease add your tourism PDF files to:")
        print(f"   {TOURISM_FOLDER}\n")
        return False
    
    print(f"✅ Found {len(pdf_files)} PDF file(s):\n")
    
    total_size = 0
    for i, pdf in enumerate(sorted(pdf_files), 1):
        file_path = os.path.join(TOURISM_FOLDER, pdf)
        size_mb = os.path.getsize(file_path) / (1024 * 1024)
        total_size += size_mb
        
        status = "✅" if size_mb < 10 else "⚠️"
        print(f"   {i}. {status} {pdf}")
        print(f"      Size: {size_mb:.2f} MB")
    
    print(f"\n📊 Total dataset size: {total_size:.2f} MB\n")
    
    # Recommendations
    if len(pdf_files) < 9:
        print(f"💡 You have {len(pdf_files)} files. Consider adding {9 - len(pdf_files)} more for comprehensive coverage.")
    elif len(pdf_files) == 9:
        print("🎯 Perfect! You have the recommended 9 PDF files.")
    else:
        print(f"✨ Great! You have {len(pdf_files)} PDF files for extensive coverage.")
    
    print("\n" + "=" * 60)
    print("🚀 Ready to use! Run: streamlit run src/app_cag.py")
    print("=" * 60 + "\n")
    
    return True

if __name__ == "__main__":
    success = check_pdfs()
    sys.exit(0 if success else 1)
