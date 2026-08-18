from pathlib import Path
import json, os, re, sys
from itertools import zip_longest

ROOT = Path(__file__).parent
APP_DIR = ROOT / 'test_app_v19'
REAL_APP = APP_DIR / 'app.py'

if not REAL_APP.exists():
    raise RuntimeError('test_app_v19/app.py is missing from the repository.')

os.chdir(APP_DIR)
sys.path.insert(0, str(APP_DIR))
os.environ.setdefault('OPENAI_MODEL', 'gpt-4.1-mini')


def _split_source_sentences(text, hebrew=False):
    text = ' '.join(str(text or '').split()).strip()
    if not text:
        return []
    pattern = r'(?<=[.!?׃])\s+' if hebrew else r'(?<=[.!?])\s+'
    parts = [x.strip() for x in re.split(pattern, text) if x.strip()]
    return parts or [text]


def _interleave_sefaria_audio(hebrew_text, english_text):
    he = _split_source_sentences(hebrew_text, hebrew=True)
    en = _split_source_sentences(english_text, hebrew=False)
    spoken = []
    for h, e in zip_longest(he, en, fillvalue=''):
        if h:
            spoken.append(h)
        if e:
            spoken.append(e)
    return '\n\n'.join(spoken)


# Bilingual repair pass: ONLY Ivrit + English mode gets AI translation.
import generator as _generator
_original_generate_ai = _generator.generate_ai


def _json_list(raw):
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', str(raw or '').strip(), flags=re.S)
    try:
        v = json.loads(raw)
        return v if isinstance(v, list) else []
    except Exception:
        return []


def _ensure_bilingual(test, config):
    if config.get('test_version') != 'ivrit_english' or not test:
        return test
    key = (os.getenv('OPENAI_API_KEY') or '').strip()
    if not key:
        return test
    missing = []
    for i, q in enumerate(test):
        if not str(q.get('prompt_en') or '').strip() or (str(q.get('answer') or '').strip() and not str(q.get('answer_en') or '').strip()):
            missing.append({'index': i, 'prompt_he': str(q.get('prompt') or ''), 'answer_he': str(q.get('answer') or '')})
    if not missing:
        return test
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key)
        prompt = '''Translate these Hebrew Chumash test items into clear, faithful English. Return VALID JSON LIST ONLY. Each object: index, prompt_en, answer_en. Do not alter the Hebrew and do not add Torah content. The English question appears directly below the Hebrew question; the English answer appears directly below the Hebrew answer.'''
        r = client.responses.create(model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'), input=prompt + '\n\n' + json.dumps(missing, ensure_ascii=False))
        by_i = {}
        for x in _json_list(r.output_text):
            try:
                by_i[int(x.get('index'))] = x
            except Exception:
                pass
        for i, q in enumerate(test):
            tr = by_i.get(i)
            if not tr:
                continue
            if not str(q.get('prompt_en') or '').strip():
                q['prompt_en'] = str(tr.get('prompt_en') or '').strip()
            if str(q.get('answer') or '').strip() and not str(q.get('answer_en') or '').strip():
                q['answer_en'] = str(tr.get('answer_en') or '').strip()
    except Exception:
        pass
    return test


def _generate_ai_v20(config, *args, **kwargs):
    return _ensure_bilingual(_original_generate_ai(config, *args, **kwargs), config)

_generator.generate_ai = _generate_ai_v20

source = REAL_APP.read_text(encoding='utf-8')

# Version badge/title for deployed build.
source = source.replace('Test App v19', 'Test App v20').replace('VERSION 19', 'VERSION 20').replace('v19-badge', 'v20-badge')

# Preserve current page when switching Hebrew/English by giving the language
# selector a stable widget key and changing only ui_lang.
old_lang = """    lang_label = st.segmented_control(\n        'Language / שפה',\n        ['עברית', 'English'],\n        default='עברית' if st.session_state.ui_lang == 'he' else 'English'\n    )\n    if lang_label:\n        st.session_state.ui_lang = 'he' if lang_label == 'עברית' else 'en'\n"""
new_lang = """    if 'language_selector' not in st.session_state:\n        st.session_state.language_selector = 'עברית' if st.session_state.ui_lang == 'he' else 'English'\n    lang_label = st.segmented_control(\n        'Language / שפה',\n        ['עברית', 'English'],\n        key='language_selector'\n    )\n    if lang_label:\n        st.session_state.ui_lang = 'he' if lang_label == 'עברית' else 'en'\n"""
source = source.replace(old_lang, new_lang)

# Change Question fix.
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

# Sefaria audio: Hebrew sentence -> matching English sentence; source only.
source = source.replace(
    "            speech_text = f\"{src.get('he','')}\\n\\n{src.get('en','')}\\n\\n{expl}\"\n",
    "            speech_text = _interleave_sefaria_audio(src.get('he',''), src.get('en',''))\n"
)
source = source.replace(
    "            speech_text = f\"{src.get('he','')}\\n\\n{src.get('en','')}\"\n",
    "            speech_text = _interleave_sefaria_audio(src.get('he',''), src.get('en',''))\n"
)
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
