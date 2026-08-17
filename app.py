from pathlib import Path
import shutil, sys, zipfile

ROOT = Path(__file__).parent
bundle = ROOT / 'test_app_v19.zip'
if not bundle.exists():
    raise RuntimeError("test_app_v19.zip is missing from the repository. Upload that ZIP file to the repository root, then Streamlit will restart automatically.")

extract_dir = Path('/tmp/chumash_test_app_v19')
marker = extract_dir / '.ready'

if not marker.exists():
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle, 'r') as zf:
        zf.testzip()
        zf.extractall(extract_dir)
    marker.write_text('ok', encoding='utf-8')

candidates = [p for p in extract_dir.rglob('app.py') if p != Path(__file__)]
if not candidates:
    raise RuntimeError('Could not find bundled app.py after extraction.')

real_app = max(candidates, key=lambda p: len(p.parts))
sys.path.insert(0, str(real_app.parent))
code = compile(real_app.read_text(encoding='utf-8'), str(real_app), 'exec')
exec(code, globals(), globals())
