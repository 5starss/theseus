import os
from pathlib import Path

def setup_complex_test_dir():
    base = Path('test_dir/complex_case')
    subdir = base / 'subdir'
    os.makedirs(subdir, exist_ok=True)
    
    files = {
        base / 'module_a.py': 'import module_b\nimport module_c as mc\nfrom . import module_d\n# Circular import test\nimport module_a\ndef func_a(): pass\n',
        base / 'module_b.py': 'from module_a import func_a\ndef func_b(): pass\n',
        base / 'module_c.py': 'def func_c(): pass\n',
        base / 'module_d.py': 'def func_d(): pass\n',
        subdir / 'module_e.py': 'from ..module_a import func_a\ndef func_e(): pass\n',
    }
    
    for path, content in files.items():
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    print("Complex test directory setup complete.")

if __name__ == "__main__":
    setup_complex_test_dir()
