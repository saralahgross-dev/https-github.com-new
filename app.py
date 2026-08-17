from pathlib import Path
import base64, io, sys, zipfile

ROOT = Path(__file__).parent
parts = []
for p in sorted(ROOT.glob('bundle_part_*.txt')):
    parts.append(p.read_text(encoding='utf-8').strip())

if not parts:
    raise RuntimeError('Deployment bundle is missing.')

payload = base64.b64decode(''.join(parts))
extract_dir = Path('/tmp/chumash_test_app_v19')
extract_dir.mkdir(parents=True, exist_ok=True)

marker = extract_dir / '.ready'
if not marker.exists():
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        zf.extractall(extract_dir)
    marker.write_text('ok', encoding='utf-8')

candidates = list(extract_dir.rglob('app.py'))
if not candidates:
    raise RuntimeError('Could not find bundled app.py after extraction.')

real_app = max(candidates, key=lambda p: len(p.parts))
sys.path.insert(0, str(real_app.parent))
code = compile(real_app.read_text(encoding='utf-8'), str(real_app), 'exec')
exec(code, globals(), globals())
