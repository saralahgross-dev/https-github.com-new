from pathlib import Path
import os, re, sys
from itertools import zip_longest

ROOT = Path(__file__).parent
APP_DIR = ROOT / 'test_app_v19'
REAL_APP = APP_DIR / 'app.py'

if not REAL_APP.exists():
    raise RuntimeError('test_app_v19/app.py is missing from the repository.')

os.chdir(APP_DIR)
sys.path.insert(0, str(APP_DIR))


def _split_source_sentences(text, hebrew=False):
    text = ' '.join(str(text or '').split()).strip()
    if not text:
        return []
    # Sefaria Hebrew often uses sof-pasuk; English uses normal sentence punctuation.
    pattern = r'(?<=[.!?׃])\s+' if hebrew else r'(?<=[.!?])\s+'
    parts = [x.strip() for x in re.split(pattern, text) if x.strip()]
    return parts or [text]


def _interleave_sefaria_audio(hebrew_text, english_text):
    """Hebrew sentence, then its English Sefaria translation, repeatedly."""
    he = _split_source_sentences(hebrew_text, hebrew=True)
    en = _split_source_sentences(english_text, hebrew=False)
    spoken = []
    for h, e in zip_longest(he, en, fillvalue=''):
        if h:
            spoken.append(h)
        if e:
            spoken.append(e)
    return '\n\n'.join(spoken)


source = REAL_APP.read_text(encoding='utf-8')

# Streamlit fix for Change Question: queue the replacement, rerun, then clear
# old widget-state values before recreating that question's widgets.
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

# Sefaria audio: source-only, bilingual and interleaved sentence by sentence.
# Hebrew sentence 1 -> English sentence 1 -> Hebrew sentence 2 -> English sentence 2.
source = source.replace(
    "            speech_text = f\"{src.get('he','')}\\n\\n{src.get('en','')}\\n\\n{expl}\"\n",
    "            speech_text = _interleave_sefaria_audio(src.get('he',''), src.get('en',''))\n"
)
source = source.replace(
    "            speech_text = f\"{src.get('he','')}\\n\\n{src.get('en','')}\"\n",
    "            speech_text = _interleave_sefaria_audio(src.get('he',''), src.get('en',''))\n"
)
# Notes-based Lecture Prep also reads exact Sefaria source bilingually; do not
# insert the teacher-topic/explanation into the source playback.
source = source.replace(
    "                            spoken_parts.append(f\"{mf}. {bs.get('he','')} {bs.get('en','')} {item.get('topic','')} {item.get('details','')}\")\n",
    "                            spoken_parts.append(_interleave_sefaria_audio(bs.get('he',''), bs.get('en','')))\n"
)
source = source.replace(
    "            st.caption('לחיצה על Play מתחילה את הסוכן לדבר; אפשר לעצור, להשהות ולשנות מהירות עד 2×. אפשר גם להקליט או לכתוב שאלה נוספת ולהכין שוב.' if rtl else 'Play starts the agent speaking. Pause, stop, or change speed up to 2×; then record or type another question and prepare again.')\n",
    "            st.caption('Play קורא משפט בעברית מ-Sefaria ואז את התרגום האנגלי של אותו משפט, וחוזר כך לאורך המקור.' if rtl else 'Play reads each Hebrew Sefaria sentence followed immediately by its English translation, then continues through the source.')\n"
)

code = compile(source, str(REAL_APP), 'exec')
exec(code, globals(), globals())
