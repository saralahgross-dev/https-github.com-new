from pathlib import Path
import os, sys

ROOT = Path(__file__).parent
APP_DIR = ROOT / 'test_app_v19'
REAL_APP = APP_DIR / 'app.py'

if not REAL_APP.exists():
    raise RuntimeError('test_app_v19/app.py is missing from the repository.')

os.chdir(APP_DIR)
sys.path.insert(0, str(APP_DIR))
source = REAL_APP.read_text(encoding='utf-8')

# Streamlit fix: changing a question previously tried to delete widget-state keys
# after those widgets had already been created in the same run. Depending on the
# Streamlit version this can make the Change Question button appear to do nothing
# (or raise a session-state exception). Queue the replacement, rerun, then clear
# the old widget keys BEFORE the question widgets are instantiated.
source = source.replace(
    "        draft = st.session_state['draft']\n        edited = []\n",
    "        pending_replacement = st.session_state.pop('_pending_question_replacement', None)\n"
    "        if pending_replacement:\n"
    "            pending_index, pending_question = pending_replacement\n"
    "            if 0 <= int(pending_index) < len(st.session_state.get('draft', [])):\n"
    "                st.session_state['draft'][int(pending_index)] = pending_question\n"
    "                for prefix in ('pr','pre','an','ane','so','df','approved_'):\n"
    "                    st.session_state.pop(f'{prefix}{int(pending_index)}', None)\n"
    "        draft = st.session_state['draft']\n"
    "        edited = []\n"
)

source = source.replace(
    "                            st.session_state['draft'][i] = replacement[0]\n"
    "                            for prefix in ('pr','pre','an','ane','so','df','approved_'):\n"
    "                                st.session_state.pop(f'{prefix}{i}', None)\n"
    "                            st.rerun()\n",
    "                            st.session_state['_pending_question_replacement'] = (i, replacement[0])\n"
    "                            st.rerun()\n"
)

code = compile(source, str(REAL_APP), 'exec')
exec(code, globals(), globals())
