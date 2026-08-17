# Test App v19

Chumash test generator, checker/grader, curriculum library, Sefaria source verification, and lecture/audio preparation.

## Upgrade behavior
Version 19 automatically scans sibling `test_app_v*` folders for prior `test_app.db` files and merges saved curriculum files, indexed notes, prior tests, answer guides/Test IDs, and question history into the current database without deleting the older copies.

## Start
```bash
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```
