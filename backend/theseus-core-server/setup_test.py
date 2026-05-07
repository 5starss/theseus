import os
from pathlib import Path

def setup_test_dir():
    base = Path('test_dir')
    subdir = base / 'subdir'
    os.makedirs(subdir, exist_ok=True)
    
    files = {
        base / 'a.py': 'import os\nimport b\ndef func_a():\n    pass\n',
        base / 'b.py': 'from subdir.c import func_c\ndef func_b():\n    pass\n',
        subdir / 'c.py': 'def func_c():\n    pass\n',
        base / 'main.py': 'from a import func_a\nfrom b import func_b\nimport sys\n'
    }
    
    for path, content in files.items():
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
    print("Test directory setup complete.")

if __name__ == "__main__":
    setup_test_dir()
