from pathlib import Path
exec((Path(__file__).parent / '_app_impl.py').read_text(encoding='utf-8'))
