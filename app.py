from pathlib import Path
import os, sys

ROOT = Path(__file__).parent
APP_DIR = ROOT / 'test_app_v19'
REAL_APP = APP_DIR / 'app.py'

if not REAL_APP.exists():
    raise RuntimeError('test_app_v19/app.py is missing from the repository.')

os.chdir(APP_DIR)
sys.path.insert(0, str(APP_DIR))
code = compile(REAL_APP.read_text(encoding='utf-8'), str(REAL_APP), 'exec')
exec(code, globals(), globals())
