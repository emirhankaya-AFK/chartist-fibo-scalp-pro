import py_compile
import os
import sys
import glob

py_files = glob.glob("*.py")
print(f"Found {len(py_files)} Python files to audit: {py_files}")

errors = []
for file in py_files:
    try:
        py_compile.compile(file, doraise=True)
        print(f"✅ {file} compiled successfully.")
    except Exception as e:
        print(f"❌ {file} compilation error: {e}")
        errors.append((file, str(e)))

if errors:
    print(f"\nFound {len(errors)} compilation errors!")
else:
    print("\nAll Python files compiled cleanly.")
