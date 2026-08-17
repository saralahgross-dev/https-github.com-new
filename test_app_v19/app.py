import os

import streamlit as st
from pathlib import Path

from storage import *
from ingest import ingest_file, openai_ready as ingest_ai_ready
from generator import (
    SECTION_META, generate_ai, generate_local, openai_ready,
    heb_num, heb_label, sefaria_url, allowed_meforshim_from_curriculum
)
from sefaria_client import get_context, as_prompt_text, ref_url, get_chapter_lengths, get_verse_count
from exporter import export_test_docx, export_answer_key_docx
from lecture import get_bilingual_source, speech_player, lecture_explanation, transcribe_audio, notes_lecture_plan, ai_ready as lecture_ai_ready, tts_audio_bytes, mac_tts_audio_bytes, basic_agent_script
from review_grading import local_check, ai_check, parse_student_answers, local_grade, ai_grade, ai_ready as grading_ai_ready
import seed_data

st.set_page_config(
    page_title='Test App v19',
    page_icon='📜',
    layout='wide',
    initial_sidebar_state='collapsed'
)

st.markdown("""
<style>
    .stApp { background: #fbfaf7; }
    .block-container { max-width: 1180px; padding-top: 1.5rem; padding-bottom: 3rem; }
    .hero {
        background: linear-gradient(135deg, #f3eadb 0%, #fffaf1 100%);
        border: 1px solid #e7dac5;
        border-radius: 22px;
        padding: 1.35rem 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 18px rgba(70,50,30,.05);
    }
    .hero h1 { margin: 0 0 .25rem 0; font-size: 2rem; }
    .hero p { margin: 0; color: #63584c; }
    .rtl { direction: rtl; text-align: right; }
    .step-card {
        background: white;
        border: 1px solid #ece7df;
        border-radius: 16px;
        padding: 1rem 1.05rem;
        margin-bottom: .7rem;
    }
    [data-testid="stMetric"] {
        background: white;
        border: 1px solid #ece7df;
        border-radius: 14px;
        padding: .5rem .75rem;
    }
    .small-note { color:#70675d; font-size:.9rem; }
    .v19-badge { display:inline-block; padding:.18rem .55rem; border-radius:999px; background:#183a2a; color:white; font-size:.78rem; font-weight:700; margin-bottom:.55rem; }
    .source-box { background:#fff; border:1px solid #e8e1d8; border-radius:16px; padding:1rem; margin:.6rem 0; }
    .source-he { direction:rtl; text-align:right; font-size:1.12rem; line-height:1.8; }
    .source-en { font-size:.98rem; line-height:1.55; color:#4f4942; }
    .status-pass { background:#eef8f1; border:1px solid #cae7d1; border-radius:12px; padding:.6rem; }
</style>
""", unsafe_allow_html=True)

if 'ui_lang' not in st.session_state:
    st.session_state.ui_lang = 'he'

head_left, head_right = st.columns([5, 1.4])
with head_right:
    lang_label = st.segmented_control(
        'Language / שפה',
        ['עברית', 'English'],
        default='עברית' if st.session_state.ui_lang == 'he' else 'English'
    )
    if lang_label:
        st.session_state.ui_lang = 'he' if lang_label == 'עברית' else 'en'

L = st.session_state.ui_lang
rtl = L == 'he'

TXT = {
'he': {
    'title':'Test App v19 — מחולל מבחני חומש',
    'subtitle':'בחרי חומר, מקור, סגנון ורמת קושי — צרי מבחן, ערכי אותו, שמרי והורידי ל-Word עם מפתח תשובות.',
    'build':'🧪 יצירת מבחן',
    'curr':'📚 חומר לימוד קבוע',
    'review':'✅ בודק + ציונים',
    'lecture':'🎧 הכנת שיעור',
    'saved':'💾 מבחנים שמורים',
    'params':'א. בחרי את החומר',
    'perek':'פרק',
    'start':'פסוק התחלה',
    'end':'פסוק סיום',
    'difficulty':'רמת קושי',
    'test_version':'גרסת המבחן',
    'ivrit_only':'עברית בלבד',
    'ivrit_english':'עברית + תרגום לאנגלית',
    'style':'ב. בחרי סגנון יצירה',
    'existing':'מבוסס על מבחנים קיימים',
    'notes':'שאלות חדשות המבוססות על הערות PDF',
    'upload_for_test':'ג. מקור נוסף למבחן הזה (אופציונלי)',
    'upload_help':'העלי דף עבודה, הערות או מבחן קודם שתרצי שהמבחן הנוכחי יתבסס עליו באופן מיוחד.',
    'sections':'ד. בחרי חלקים וכמות שאלות',
    'generate':'✨ צרי את המבחן',
    'name':'שם המבחן',
    'save':'💾 שמרי באפליקציה',
    'download':'📄 הורידי Word + מפתח תשובות',
    'check':'🔎 בדיקה ב-Sefaria',
    'saved_title':'מבחנים שמורים',
    'load':'פתחי',
    'delete':'מחקי',
    'created':'נוצר',
    'source_ready':'מקורות זמינים',
    'draft':'טיוטת מבחן — ניתן לערוך',
    'answer':'מפתח תשובה',
    'source':'פסוק מקור מדויק',
    'keep':'השאירי שאלה'
},
'en': {
    'title':'Test App v19 — Chumash Test Generator',
    'subtitle':'Choose material, sources, style and difficulty. Generate, edit, save, and download every test to Word with an answer key.',
    'build':'🧪 Build Test',
    'curr':'📚 Curriculum Library',
    'review':'✅ Checker + Grading',
    'lecture':'🎧 Lecture Prep',
    'saved':'💾 Saved Tests',
    'params':'1. Choose the material',
    'perek':'Chapter',
    'start':'Starting verse',
    'end':'Ending verse',
    'difficulty':'Difficulty',
    'test_version':'Test Version',
    'ivrit_only':'Ivrit Only',
    'ivrit_english':'Ivrit + English Translation',
    'style':'2. Choose generation style',
    'existing':'Based on existing tests',
    'notes':'New questions based on PDF notes',
    'upload_for_test':'3. Extra source for this test (optional)',
    'upload_help':'Upload a worksheet, notes, or a prior test you want this specific test to use as additional context.',
    'sections':'4. Choose sections and question counts',
    'generate':'✨ Generate Test',
    'name':'Test name',
    'save':'💾 Save in app',
    'download':'📄 Download Word + Answer Key',
    'check':'🔎 Check in Sefaria',
    'saved_title':'Saved Tests',
    'load':'Open',
    'delete':'Delete',
    'created':'Created',
    'source_ready':'Available sources',
    'draft':'Editable Test Draft',
    'answer':'Answer key',
    'source':'Exact source pasuk',
    'keep':'Keep question'
}
}[L]

with head_left:
    cls = 'rtl' if rtl else ''
    st.markdown(
        f'<div class="hero {cls}"><span class="v19-badge">VERSION 19</span><h1>{TXT["title"]}</h1><p>{TXT["subtitle"]}</p></div>',
        unsafe_allow_html=True
    )

NAV_LABELS = {'build':TXT['build'],'curr':TXT['curr'],'review':TXT['review'],'lecture':TXT['lecture'],'saved':TXT['saved']}
if 'active_page' not in st.session_state:
    st.session_state.active_page = 'build'
active_page = st.radio(
    'Navigation',
    ['build','curr','review','lecture','saved'],
    key='active_page',
    format_func=lambda x: NAV_LABELS[x],
    horizontal=True,
    label_visibility='collapsed'
)


def format_perek(n):
    return heb_label(n, 'פרק') if rtl else str(n)

def format_pasuk(n):
    return heb_label(n, 'פסוק') if rtl else str(n)

def temporary_ingest(uploaded_files, source_type, perek_hint):
    curriculum_items, style_items, summaries = [], [], []
    if not uploaded_files:
        return curriculum_items, style_items, summaries
    for f in uploaded_files:
        raw, structured = ingest_file(f.getvalue(), f.name, source_type, perek_hint)
        summaries.append({
            'name': f.name,
            'source_type': source_type,
            'summary': structured.get('summary',''),
            'raw_excerpt': raw[:3000]
        })
        if source_type == 'prior_test':
            for x in structured.get('style_examples', []):
                x = dict(x)
                x['source_name'] = f.name
                style_items.append(x)
        else:
            for x in structured.get('curriculum_items', []):
                x = dict(x)
                x['source_type'] = source_type
                x['source_name'] = f.name
                curriculum_items.append(x)
            # Worksheets may also teach question style.
            for x in structured.get('style_examples', []):
                x = dict(x)
                x['source_name'] = f.name
                style_items.append(x)
    return curriculum_items, style_items, summaries


@st.cache_data(ttl=86400, show_spinner=False)
def shemot_chapter_lengths():
    """
    Read Sefer Shemot's structure from Sefaria's Shape API.
    Falls back to the standard 40-perek Shemot structure if Sefaria is
    temporarily unavailable, so the UI never offers impossible pesukim.
    """
    try:
        return get_chapter_lengths('Exodus')
    except Exception:
        # Standard Sefer Shemot verse counts by perek, used only as offline fallback.
        return [
            22,25,22,31,23,30,25,32,35,29,
            10,51,22,31,27,36,16,27,25,26,
            37,30,33,18,40,37,21,43,46,38,
            18,35,23,35,35,38,29,31,43,38
        ]


# ===================== BUILD TEST =====================
if active_page == 'build':
    left, right = st.columns([1, 1.8], gap='large')

    with left:
        st.markdown(f'<div class="step-card"><b>{TXT["params"]}</b></div>', unsafe_allow_html=True)

        chapter_lengths = shemot_chapter_lengths()
        perek_options = list(range(1, len(chapter_lengths) + 1))

        if rtl:
            perek = st.selectbox(
                TXT['perek'],
                perek_options,
                index=min(2, len(perek_options)-1),
                format_func=format_perek
            )
        else:
            perek = st.selectbox(
                TXT['perek'],
                perek_options,
                index=min(2, len(perek_options)-1),
                format_func=lambda n: str(n)
            )

        max_pasuk = chapter_lengths[int(perek) - 1]
        pasuk_options = list(range(1, max_pasuk + 1))

        # Keep prior selection only when it is valid for the newly-selected perek.
        if st.session_state.get('selected_start_pasuk') not in pasuk_options:
            st.session_state['selected_start_pasuk'] = 1
        if st.session_state.get('selected_end_pasuk') not in pasuk_options:
            st.session_state['selected_end_pasuk'] = max_pasuk

        if rtl:
            start = st.selectbox(
                TXT['start'],
                pasuk_options,
                index=pasuk_options.index(st.session_state['selected_start_pasuk']),
                format_func=format_pasuk,
                key='selected_start_pasuk_widget'
            )
            end_options = [x for x in pasuk_options if x >= int(start)]
            default_end = st.session_state.get('selected_end_pasuk', end_options[-1])
            if default_end not in end_options:
                default_end = end_options[-1]
            end = st.selectbox(
                TXT['end'],
                end_options,
                index=end_options.index(default_end),
                format_func=format_pasuk,
                key='selected_end_pasuk_widget'
            )
        else:
            start = st.selectbox(
                TXT['start'],
                pasuk_options,
                index=pasuk_options.index(st.session_state['selected_start_pasuk']),
                format_func=lambda n: str(n),
                key='selected_start_pasuk_widget'
            )
            end_options = [x for x in pasuk_options if x >= int(start)]
            default_end = st.session_state.get('selected_end_pasuk', end_options[-1])
            if default_end not in end_options:
                default_end = end_options[-1]
            end = st.selectbox(
                TXT['end'],
                end_options,
                index=end_options.index(default_end),
                format_func=lambda n: str(n),
                key='selected_end_pasuk_widget'
            )

        st.session_state['selected_start_pasuk'] = int(start)
        st.session_state['selected_end_pasuk'] = int(end)

        st.caption(
            (f"פרק {heb_num(perek)} כולל {heb_num(max_pasuk)} פסוקים לפי Sefaria."
             if rtl else
             f"Chapter {perek} contains {max_pasuk} verses according to Sefaria.")
        )

        difficulty = st.slider(TXT['difficulty'], 1, 10, 5)

        test_version_label = st.radio(
            TXT['test_version'],
            [TXT['ivrit_only'], TXT['ivrit_english']],
            index=0,
            horizontal=True
        )
        test_version = 'ivrit_only' if test_version_label == TXT['ivrit_only'] else 'ivrit_english'
        if test_version == 'ivrit_english' and not openai_ready():
            bilingual_key = st.text_input(
                'OpenAI API key לתרגום עברית + אנגלית' if rtl else 'OpenAI API key for Hebrew + English translation',
                type='password', key='build_bilingual_api_key',
                help='Used so every question has Hebrew first and English directly underneath.'
            )
            if bilingual_key:
                os.environ['OPENAI_API_KEY'] = bilingual_key
            else:
                st.warning('כדי להבטיח שכל שאלה תופיע בעברית ואחריה אנגלית, הוסיפי מפתח API.' if rtl else 'Add an API key so every question can be shown Hebrew first with English directly underneath.')

        st.markdown(f'<div class="step-card"><b>{TXT["upload_for_test"]}</b></div>', unsafe_allow_html=True)
        specific_type = st.selectbox(
            'סוג מקור' if rtl else 'Source type',
            ['notes', 'worksheet', 'prior_test'],
            format_func=lambda x: {'worksheet':'דף עבודה / Worksheet','notes':'הערות / Notes','prior_test':'מבחן קודם / Prior test'}[x],
            key='build_specific_type'
        )
        mode = 'existing_tests' if specific_type == 'prior_test' else 'notes'
        st.caption(TXT['upload_help'])
        test_specific_files = st.file_uploader(
            'קבצים למבחן הזה' if rtl else 'Files for this test',
            type=['pdf','docx','txt','md'],
            accept_multiple_files=True,
            key='build_specific_uploads'
        )
        only_use_uploaded = st.checkbox(
            'השתמשי רק בקבצים האלה' if rtl else 'Only use this',
            value=False,
            key='only_use_uploaded',
            help=('אם מסומן, המבחן הזה יתבסס רק על הקבצים שהועלו כאן.' if rtl else 'When checked, this test uses only the files uploaded here.')
        )

        with st.expander('📚 הוסיפי חומר לימוד קבוע' if rtl else '📚 Add Permanent Curriculum', expanded=False):
            if 'perm_upload_nonce' not in st.session_state:
                st.session_state.perm_upload_nonce = 0
            perm_file = st.file_uploader(
                'קובץ אחד בכל פעם' if rtl else 'One file at a time',
                type=['pdf','docx','txt','md','png','jpg','jpeg','webp'],
                key=f'perm_upload_{st.session_state.perm_upload_nonce}'
            )
            perm_type = st.selectbox('סוג חומר' if rtl else 'Material type', ['notes','worksheet','prior_test'], key='perm_type_build')
            if perm_file and st.button('💾 שמרי קובץ' if rtl else '💾 Save File', key='save_perm_build', type='primary'):
                try:
                    raw, structured = ingest_file(perm_file.getvalue(), perm_file.name, perm_type, int(perek))
                    sid = add_source(perm_file.name, perm_type, perek=int(perek), extracted_text=raw, metadata=structured)
                    add_curriculum_items(sid, structured.get('curriculum_items', []), default_type=perm_type)
                    add_style_examples(sid, structured.get('style_examples', []))
                    st.session_state.perm_upload_nonce += 1
                    st.session_state['just_saved_perm'] = perm_file.name
                    st.rerun()
                except Exception as e:
                    st.error(('לא ניתן לשמור את הקובץ: ' if rtl else 'Could not save file: ') + str(e))
            if st.session_state.get('just_saved_perm'):
                st.success(('נשמר והחלון נוקה: ' if rtl else 'Saved and uploader cleared: ') + st.session_state['just_saved_perm'])
                if st.button('➕ הוסיפי קובץ נוסף' if rtl else '➕ Add Additional File', key='add_more_perm'):
                    st.session_state.pop('just_saved_perm', None)
                    st.rerun()

        st.markdown(f'<div class="step-card"><b>{TXT["sections"]}</b></div>', unsafe_allow_html=True)
        section_choices = list(SECTION_META)
        def shown(section):
            return section if rtl else SECTION_META[section]

        selected_labels = st.multiselect(
            'Question sections / חלקי המבחן',
            [shown(s) for s in section_choices],
            default=[shown(s) for s in [
                'על מי / על מה נאמר',
                'בקשר למה למדנו',
                'שאלת ותשובת רש״י',
                'שאלות קצרות',
                'מפרשים'
            ]],
            label_visibility='collapsed'
        )
        reverse = {shown(s): s for s in section_choices}
        sections = [reverse[x] for x in selected_labels]
        counts = {}
        for idx, section in enumerate(sections, 1):
            label_num = heb_num(idx) if rtl else str(idx)
            counts[section] = st.number_input(
                f'{label_num}. {shown(section)}',
                0, 30, 3,
                key='count_' + section
            )

        manual_meforshim_text = ''
        if 'מפרשים' in sections:
            st.markdown('**מפרשים — מקור מההערות בלבד**' if rtl else '**Mefarshim — notes-bound source**')
            st.caption(
                'המערכת תחפש מפרשים רק בהערות הרלוונטיות. אם אין הערות, אפשר להדביק כאן חומר מפרשים משלך.'
                if rtl else
                'The app will use only mefarshim found in relevant notes. If none are found, you may paste your own mefarshim material here.'
            )
            manual_meforshim_text = st.text_area(
                'חומר מפרשים נוסף (אופציונלי)' if rtl else 'Manual mefarshim material (optional)',
                key='manual_meforshim_text',
                height=120,
                placeholder='לדוגמה: רמב״ן על פסוק ג׳ — ...' if rtl else 'Example: Ramban on verse 3 — ...'
            )

        seed = 2026  # backend-only; intentionally hidden from teacher UI

        if mode == 'notes' and not openai_ready():
            st.warning(
                'יצירת שאלות חדשות מהערות סרוקות/בכתב יד דורשת חיבור AI בשרת.'
                if rtl else
                'New questions from scanned/handwritten notes require the AI backend.'
            )

        generate = st.button(TXT['generate'], type='primary', use_container_width=True)

    with right:
        st.markdown(f'<div class="step-card"><b>{TXT["source_ready"]}</b></div>', unsafe_allow_html=True)
        ns, ni, ne = source_counts()
        a, b, c = st.columns(3)
        a.metric('מקורות' if rtl else 'Sources', ns)
        b.metric('נושאי לימוד' if rtl else 'Curriculum topics', ni)
        c.metric('דוגמאות מבחן' if rtl else 'Test examples', ne)

        curriculum_preview = get_curriculum(int(perek), int(start), int(end))
        note_count = sum(1 for x in curriculum_preview if x.get('source_type') == 'notes')
        st.write(
            f'פריטים רלוונטיים: **{len(curriculum_preview)}** · הדגשות מהערות PDF: **{note_count}**'
            if rtl else
            f'Relevant indexed items: **{len(curriculum_preview)}** · PDF-note highlights: **{note_count}**'
        )

        try:
            ctx = get_context(int(perek), int(start), int(end))
            range_label = (
                f"שמות {heb_num(perek)}:{heb_num(start)}–{heb_num(end)}"
                if rtl else
                f"Shemot {perek}:{start}-{end}"
            )
            st.link_button(TXT['check'] + f" — {range_label}", ctx.get('base_url') or ref_url(ctx.get('base_ref')))
            with st.expander('הצג פסוקים מדויקים ומפרשים' if rtl else 'View exact pesukim and meforshim'):
                for pasuk_num, pasuk_text in sorted((ctx.get('verses') or {}).items()):
                    label = f"פסוק {heb_num(pasuk_num)}" if rtl else f"Verse {pasuk_num}"
                    st.markdown(f"**{label}** — {pasuk_text}")
                    st.markdown(f"[{TXT['check']} — {label}]({ref_url(f'Exodus {perek}:{pasuk_num}')})")
                for meforash, items in ctx.get('commentaries', {}).items():
                    if items:
                        st.markdown(f"**{meforash}**")
                        for item in items[:6]:
                            anchor = item.get('anchor') or ''
                            source_ref = item.get('source_ref','source')
                            anchor_note = f" — {anchor}" if anchor else ""
                            st.markdown(f"- [{source_ref}]({item.get('url','')}){anchor_note}")
        except Exception as e:
            ctx = {}
            st.caption(f'Sefaria unavailable: {e}')

        if curriculum_preview:
            with st.expander('תצוגת חומר לימוד רלוונטי' if rtl else 'Relevant curriculum preview'):
                for x in curriculum_preview[:30]:
                    st.markdown(
                        f"**{x.get('meforash') or 'Topic'} — {x.get('topic')}**  \n"
                        f"{x.get('details','')}  \n"
                        f"_Source: {x.get('source_name','')}_"
                    )

    if generate:
        if not counts or sum(counts.values()) < 1:
            st.error('Choose at least one question.')
        elif int(start) > int(end):
            st.error('Start pasuk must be before end pasuk.')
        else:
            config = {
                'perek': int(perek),
                'start': int(start),
                'end': int(end),
                'difficulty': difficulty,
                'counts': counts,
                'seed': int(seed),
                'language': 'he',
                'test_version': test_version,
                'generation_mode': mode,
                'manual_meforshim_text': manual_meforshim_text.strip()
            }

            stored_sources = [x for x in list_sources(specific_type) if x.get('perek') in (None, config['perek'])]
            stored_ids = [x['id'] for x in stored_sources]
            curriculum = get_curriculum(config['perek'], config['start'], config['end'], source_ids=stored_ids) if stored_ids else []
            styles = get_style_examples(config['perek'], list(counts), 100, source_ids=stored_ids) if stored_ids else []

            temp_curr, temp_styles, temp_summaries = [], [], []
            if test_specific_files:
                with st.spinner(
                    'קורא את המקור שהעלית למבחן הזה...'
                    if rtl else
                    'Reading the source uploaded for this test...'
                ):
                    try:
                        temp_curr, temp_styles, temp_summaries = temporary_ingest(
                            test_specific_files, specific_type, config['perek']
                        )
                    except Exception as e:
                        st.error(f'Could not read test-specific upload: {e}')

            if only_use_uploaded and test_specific_files:
                curriculum = temp_curr
                styles = temp_styles
            else:
                curriculum = temp_curr + curriculum
                styles = temp_styles + styles

            if manual_meforshim_text.strip():
                curriculum = [{
                    'source_type':'manual_meforshim',
                    'source_name':'Manual mefarshim material',
                    'perek':config['perek'],
                    'pasuk_start':config['start'],
                    'pasuk_end':config['end'],
                    'meforash':'',
                    'topic':'חומר מפרשים שהוזן ידנית',
                    'details':manual_meforshim_text.strip(),
                    'importance':10,
                }] + curriculum

            st.session_state['generation_curriculum'] = curriculum
            st.session_state['generation_styles'] = styles
            st.session_state['generation_temp_summaries'] = temp_summaries

            spinner_text = (
                'קורא חומר לימוד, בודק כל פסוק ב-Sefaria ויוצר מבחן...'
                if rtl else
                'Reading curriculum, checking exact pesukim in Sefaria, and generating...'
            )
            with st.spinner(spinner_text):
                try:
                    if not ctx:
                        ctx = get_context(config['perek'], config['start'], config['end'])
                    sef = as_prompt_text(ctx)
                except Exception as e:
                    sef = f'Sefaria unavailable: {e}'
                    ctx = {}

                try:
                    if openai_ready():
                        test = generate_ai(
                            config, curriculum, styles, sef,
                            recent_questions(config['perek']),
                            mode=mode,
                            sefaria_ctx=ctx,
                            temporary_sources=temp_summaries
                        )
                    else:
                        test = generate_local(
                            config, styles, mode=mode, sefaria_ctx=ctx, curriculum=curriculum
                        )

                    st.session_state['draft'] = test
                    st.session_state['config'] = config
                    requested_total = sum(int(v) for v in counts.values())
                    allowed_mf, mf_note_items = allowed_meforshim_from_curriculum(curriculum)
                    generated_by_section = {sec: sum(1 for q in test if q.get('section') == sec) for sec in counts}

                    # מפרשים is strictly notes/manual-source bound. If the teacher asks for
                    # more questions than the notes support, preserve the requested number of
                    # visible slots without inventing a meforash or unsupported Torah content.
                    requested_mf = int(counts.get('מפרשים', 0) or 0)
                    have_mf = generated_by_section.get('מפרשים', 0)
                    if requested_mf and have_mf < requested_mf:
                        missing_mf = requested_mf - have_mf
                        for slot_no in range(missing_mf):
                            test.append({
                                'section': 'מפרשים',
                                'prompt': '',
                                'prompt_en': '',
                                'answer': '',
                                'answer_en': '',
                                'source_ref': '',
                                'sefaria_ref': '',
                                'meforash': '',
                                'difficulty': int(config.get('difficulty', 5)),
                                'approved': False,
                                'missing_notes_slot': True,
                                'support_message_he': 'לא נמצאה שאלה נתמכת נוספת מההערות. אפשר לכתוב שאלה כאן.',
                                'support_message_en': "Couldn't find another supported question from the notes. Type your own question here.",
                            })
                        st.session_state['draft'] = test
                        generated_by_section['מפרשים'] = requested_mf
                        st.warning(
                            (f'נמצאו {have_mf} שאלות מפרשים נתמכות מתוך {requested_mf}. {missing_mf} מקומות נשארו ריקים כדי שתוכלי לכתוב שאלות משלך; לא הומצאו מפרשים.'
                             if rtl else
                             f'Found {have_mf} supported mefarshim questions out of {requested_mf}. {missing_mf} slots were left blank for you to type your own questions; no mefarshim were invented.')
                        )
                    other_missing = {sec: int(n)-generated_by_section.get(sec,0) for sec,n in counts.items() if sec != 'מפרשים' and generated_by_section.get(sec,0) < int(n)}
                    if other_missing:
                        st.warning(('חסרות שאלות בחלקים: ' if rtl else 'Missing generated questions in: ') + ', '.join(f'{k}: {v}' for k,v in other_missing.items()))
                    if not test:
                        st.warning(
                            'לא נמצאו מספיק שאלות נתמכות בחומר.'
                            if rtl else
                            'Not enough supported questions were found in the material.'
                        )
                except Exception as e:
                    st.error(f'Generation failed: {e}')

    if st.session_state.get('draft') is not None:
        st.divider()
        title_col, reset_col = st.columns([4,1])
        title_col.subheader(TXT['draft'])
        if reset_col.button('↺ אפסי מבחן' if rtl else '↺ Reset Test', use_container_width=True, key='reset_test'):
            for k in list(st.session_state.keys()):
                if k.startswith(('pr','pre','an','ane','so','df','approved_')) or k in ('draft','config','v11_check_results','v11_grade_results'):
                    st.session_state.pop(k, None)
            st.rerun()
        draft = st.session_state['draft']
        edited = []

        for i, q in enumerate(draft):
            number = heb_num(i + 1) if rtl else str(i + 1)
            section_name = shown(q.get('section')) if q.get('section') in SECTION_META else q.get('section', 'Question')
            with st.expander(f"{number}. {section_name}", expanded=True):
                if q.get('missing_notes_slot'):
                    st.info(
                        q.get('support_message_he') if rtl else q.get('support_message_en'),
                        icon='📝'
                    )
                prompt = st.text_area(
                    'שאלה בעברית' if rtl else 'Hebrew question',
                    q.get('prompt',''),
                    key=f'pr{i}',
                    height=78
                )
                prompt_en = q.get('prompt_en','')
                if st.session_state.get('config', {}).get('test_version') == 'ivrit_english':
                    prompt_en = st.text_area(
                        'תרגום לאנגלית' if rtl else 'English translation',
                        prompt_en,
                        key=f'pre{i}',
                        height=58
                    )

                answer = st.text_area(
                    'מפתח תשובה בעברית' if rtl else 'Hebrew answer key',
                    q.get('answer',''),
                    key=f'an{i}',
                    height=62
                )
                answer_en = q.get('answer_en','')
                if st.session_state.get('config', {}).get('test_version') == 'ivrit_english':
                    answer_en = st.text_area(
                        'תרגום התשובה לאנגלית' if rtl else 'English answer translation',
                        answer_en,
                        key=f'ane{i}',
                        height=54
                    )
                source = st.text_input(TXT['source'], q.get('source_ref',''), key=f'so{i}')
                diff = st.slider(TXT['difficulty'], 1, 10, int(q.get('difficulty', 5)), key=f'df{i}')

                link_cols = st.columns(2)
                if q.get('source_ref'):
                    link_cols[0].link_button(
                        ('📖 פסוק ב-Sefaria' if rtl else '📖 Pasuk in Sefaria'),
                        sefaria_url(q['source_ref'])
                    )
                if q.get('sefaria_ref') and q.get('sefaria_ref') != q.get('source_ref'):
                    label = (
                        f"🔎 {q.get('meforash') or 'מפרש'} ב-Sefaria"
                        if rtl else
                        f"🔎 {q.get('meforash') or 'Meforash'} in Sefaria"
                    )
                    link_cols[1].link_button(label, q.get('sefaria_url') or sefaria_url(q['sefaria_ref']))
                elif q.get('sefaria_url'):
                    link_cols[1].link_button(TXT['check'], q['sefaria_url'])

                if not q.get('source_ref'):
                    st.warning(
                        'לא נמצא פסוק מקור מדויק — בדקי את השאלה לפני השמירה.'
                        if rtl else
                        'Exact source pasuk was not resolved; review this question before saving.'
                    )

                action_a, action_b = st.columns(2)
                approved = action_a.checkbox('✓ השאירי שאלה' if rtl else '✓ Approve / Keep Question', value=bool(q.get('approved', False)), key=f'approved_{i}')
                if action_b.button('🔄 שני שאלה' if rtl else '🔄 Change Question', key=f'change_{i}', use_container_width=True):
                    cfg = dict(st.session_state.get('config', {}))
                    sec = q.get('section')
                    cfg['counts'] = {sec: 1}
                    try:
                        c = st.session_state.get('generation_curriculum') or get_curriculum(cfg['perek'], cfg['start'], cfg['end'])
                        sty = st.session_state.get('generation_styles') or get_style_examples(cfg['perek'], [sec], 100)
                        cctx = get_context(cfg['perek'], cfg['start'], cfg['end'])
                        rejected = list(q.get('rejected_prompts') or [])
                        rejected.append(q.get('prompt',''))
                        avoid = recent_questions(cfg['perek']) + rejected
                        replacement = []
                        for attempt in range(6):
                            cfg['seed'] = int(cfg.get('seed',2026)) + attempt + i + 1
                            if openai_ready():
                                candidate = generate_ai(cfg, c, sty, as_prompt_text(cctx), avoid, mode=cfg.get('generation_mode','notes'), sefaria_ctx=cctx, temporary_sources=st.session_state.get('generation_temp_summaries') or [])
                            else:
                                candidate = generate_local(cfg, sty, mode=cfg.get('generation_mode','existing_tests'), sefaria_ctx=cctx, curriculum=c, avoid_prompts=avoid)
                            replacement = [x for x in candidate if str(x.get('prompt','')).strip() and str(x.get('prompt','')).strip() not in rejected]
                            if replacement:
                                break
                        if replacement:
                            replacement[0]['rejected_prompts'] = rejected
                            st.session_state['draft'][i] = replacement[0]
                            for prefix in ('pr','pre','an','ane','so','df','approved_'):
                                st.session_state.pop(f'{prefix}{i}', None)
                            st.rerun()
                        else:
                            st.warning('לא נמצאה שאלה חלופית נתמכת.' if rtl else 'No supported replacement question was found.')
                    except Exception as e:
                        st.error(('לא ניתן להחליף את השאלה: ' if rtl else 'Could not replace question: ') + str(e))
                edited.append({
                    **q,
                    'prompt': prompt,
                    'prompt_en': prompt_en,
                    'answer': answer,
                    'answer_en': answer_en,
                    'source_ref': source,
                    'difficulty': diff,
                    'approved': approved,
                    'sefaria_url': q.get('sefaria_url') or sefaria_url(source)
                })

        st.session_state['draft'] = edited
        st.divider()
        st.subheader('סיום, שמירה והורדה' if rtl else 'Finalize, Save & Download')

        default_name = (
            f"מבחן שמות פרק {heb_num(st.session_state['config']['perek'])}"
            if rtl else
            f"Shemot Chapter {st.session_state['config']['perek']} Test"
        )
        name = st.text_input(TXT['name'], default_name)

        save_col, test_col, key_col = st.columns(3)
        if save_col.button(TXT['save'], use_container_width=True):
            uid = save_test(name, st.session_state['config'], st.session_state['draft'])
            st.session_state['config']['test_uid'] = uid
            st.caption(('מזהה פנימי: ' if rtl else 'Internal Test ID: ') + uid)
            remember_questions(st.session_state['draft'], st.session_state['config']['perek'])
            st.success(('נשמר: ' if rtl else 'Saved: ') + name)

        test_path = export_test_docx(st.session_state['draft'], st.session_state['config'], name)
        key_path = export_answer_key_docx(st.session_state['draft'], st.session_state['config'], name)
        test_col.download_button(
            '📄 הורידי מבחן' if rtl else '📄 Download Test',
            test_path.read_bytes(),
            file_name=f"{name} - Test.docx",
            mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            use_container_width=True
        )
        key_col.download_button(
            '🗝️ הורידי מפתח תשובות' if rtl else '🗝️ Download Answer Key',
            key_path.read_bytes(),
            file_name=f"{name} - Answer Key.docx",
            mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            use_container_width=True
        )

# ===================== CURRICULUM LIBRARY =====================
if active_page == 'curr':
    st.subheader('ספריית חומר הלימוד' if rtl else 'Curriculum Library')
    st.info(
        'כאן מוסיפים חומר קבוע ל-backend: הערות PDF בכתב יד, דפי עבודה, sheets ומבחנים קודמים. החומר הזה נשאר בהקשר של האפליקציה למבחנים עתידיים.'
        if rtl else
        'Add permanent backend context here: handwritten PDF notes, worksheets, sheets, and prior tests. These remain available for future test generation.'
    )

    files = st.file_uploader(
        'Upload PDF, DOCX, TXT',
        type=['pdf','docx','txt','md'],
        accept_multiple_files=True,
        key='library_uploads'
    )
    custom_base_name = st.text_input(
        'שם מותאם לקובץ / Custom file name',
        value='',
        help='Upload one file at a time when you want to assign a custom saved name.'
    )
    source_type = st.selectbox(
        'File type',
        ['notes','worksheet','sheet','prior_test'],
        format_func=lambda x: {
            'notes':'Notes / הערות',
            'worksheet':'Worksheet / דף עבודה',
            'sheet':'Sheet / חומר מורחב',
            'prior_test':'Prior test / מבחן קודם'
        }[x],
        key='library_source_type'
    )

    if rtl:
        perek_hint = st.selectbox(
            'פרק (אם ידוע)',
            [0] + list(range(1, 41)),
            format_func=lambda n: 'לא ידוע' if n == 0 else heb_label(n, 'פרק')
        )
    else:
        perek_hint = st.number_input(TXT['perek'] + ' hint', 0, 40, 0)

    if files and st.button('Index uploaded files', type='primary'):
        for f in files:
            message = (
                f'קורא כל עמוד PDF, כולל כתב יד: {f.name}...'
                if rtl else
                f'Reading every PDF page, including handwriting: {f.name}...'
            )
            with st.spinner(message):
                try:
                    raw, structured = ingest_file(
                        f.getvalue(), f.name, source_type, perek_hint or None
                    )
                    saved_name = custom_base_name.strip() if len(files) == 1 and custom_base_name.strip() else f.name
                    sid = add_source(
                        saved_name, source_type, 'Shemot', perek_hint or None,
                        raw, {'summary': structured.get('summary','')}
                    )
                    items = structured.get('curriculum_items', [])
                    examples = structured.get('style_examples', [])

                    if source_type == 'prior_test':
                        add_style_examples(sid, examples)
                    else:
                        for x in items:
                            x['source_type'] = source_type
                        add_curriculum_items(sid, items, source_type)
                        if examples:
                            add_style_examples(sid, examples)

                    st.success(
                        f'Indexed {f.name}: {len(items)} curriculum highlights, {len(examples)} style examples.'
                    )
                except Exception as e:
                    st.error(f'{f.name}: {e}')

    if not ingest_ai_ready():
        st.caption(
            'Handwritten/image PDF indexing requires the configured AI backend; printed PDF text is still stored.'
        )

    st.markdown('### ' + ('ספריית קבצים' if rtl else 'Curriculum Files Library'))
    st.caption(
        'בחרי פרק וסוג מקור. כשנבחר Notes, הרשימה מציגה רק קבצי הערות של אותו פרק. אפשר גם לצמצם לטווח פסוקים ולראות רק את החומר הרלוונטי אחרי ניתוח ההערות.'
        if rtl else
        'Choose a perek and source type. When Notes is selected, only note files saved for that perek are listed. You can also narrow to a pasuk range and preview only note material mapped to that range.'
    )

    lib_f1, lib_f2 = st.columns(2)
    with lib_f1:
        library_perek_filter = st.selectbox(
            'פרק לסינון' if rtl else 'Filter by perek',
            [0] + list(range(1, 41)),
            format_func=(lambda n: 'כל הפרקים' if n == 0 else heb_label(n, 'פרק')) if rtl else (lambda n: 'All chapters' if n == 0 else str(n)),
            key='library_browse_perek'
        )
    with lib_f2:
        library_type_filter = st.selectbox(
            'סוג מקור' if rtl else 'Source type',
            ['all','notes','worksheet','sheet','prior_test'],
            format_func=lambda x: {
                'all':'הכל / All','notes':'Notes / הערות','worksheet':'Worksheet / דף עבודה',
                'sheet':'Sheet / חומר מורחב','prior_test':'Prior test / מבחן קודם'
            }[x],
            key='library_browse_type'
        )

    range_start = range_end = None
    if library_perek_filter:
        try:
            lib_max = shemot_chapter_lengths()[int(library_perek_filter)-1]
        except Exception:
            lib_max = 30
        rr1, rr2 = st.columns(2)
        with rr1:
            range_start = st.selectbox('פסוק התחלה' if rtl else 'Starting verse', list(range(1, lib_max+1)), format_func=format_pasuk if rtl else str, key='library_range_start')
        with rr2:
            end_opts = list(range(int(range_start), lib_max+1))
            range_end = st.selectbox('פסוק סיום' if rtl else 'Ending verse', end_opts, format_func=format_pasuk if rtl else str, key='library_range_end')

        if library_type_filter == 'notes':
            note_preview = [x for x in get_curriculum(int(library_perek_filter), int(range_start), int(range_end)) if x.get('source_type') == 'notes']
            st.caption((f'נמצאו {len(note_preview)} פריטי הערות ממופים לטווח הפסוקים שנבחר.' if rtl else f'Found {len(note_preview)} note items mapped to the selected pasuk range.'))
            if note_preview:
                with st.expander('הצג חומר הערות בטווח' if rtl else 'Preview notes in selected range'):
                    for x in note_preview[:60]:
                        ps=x.get('pasuk_start'); pe=x.get('pasuk_end')
                        rng = f'{ps}-{pe}' if ps and pe and ps != pe else (str(ps or pe or '?'))
                        st.markdown(f"**{x.get('meforash') or x.get('topic') or 'Note'} — {rng}**  \n{x.get('details','')}")

    library_sources = list_sources()
    if library_perek_filter:
        library_sources = [x for x in library_sources if int(x.get('perek') or 0) == int(library_perek_filter)]
    if library_type_filter != 'all':
        library_sources = [x for x in library_sources if x.get('source_type') == library_type_filter]
    if library_type_filter == 'notes' and library_perek_filter and not library_sources:
        st.info('לא נמצאו קבצי Notes לפרק הזה.' if rtl else 'No notes found for this perek.')

    st.caption(
        'אפשר לשנות שם או למחוק מקור. מחיקה מסירה אותו מהקשר של יצירת מבחנים עתידיים.'
        if rtl else
        'Rename or delete any source. Deleting it removes that source from future test-generation context.'
    )
    for s in library_sources[:200]:
        perek_text = heb_num(s['perek']) if rtl and s['perek'] else (s['perek'] or '?')
        with st.expander(f"{s['name']} — {s['source_type']} — perek {perek_text}"):
            current_name = st.text_input(
                'שם הקובץ' if rtl else 'File name',
                value=s['name'],
                key=f"src_name_{s['id']}"
            )
            rc1, rc2, rc3 = st.columns([1.2, 1.2, 1])
            if rc1.button('שני שם' if rtl else 'Rename', key=f"rename_src_{s['id']}"):
                try:
                    final_name = rename_source(s['id'], current_name)
                    st.success(('השם שונה ל-' if rtl else 'Renamed to ') + final_name)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            source_row = get_source(s['id'])
            if source_row and source_row.get('raw_text'):
                rc2.download_button(
                    '📄 טקסט מקור' if rtl else '📄 Source text',
                    str(source_row.get('raw_text','')).encode('utf-8'),
                    file_name=f"{current_name}.txt",
                    mime='text/plain',
                    key=f"source_text_{s['id']}"
                )
            if rc3.button('🗑️ מחקי' if rtl else '🗑️ Delete', key=f"delete_src_{s['id']}"):
                delete_source(s['id'])
                st.success('נמחק.' if rtl else 'Deleted.')
                st.rerun()


# ===================== CHECKER + GRADING =====================
if active_page == 'review':
    st.subheader('בודק מבחן + ציונים' if rtl else 'Test Checker + Grading')
    st.caption(
        'בדקי את טיוטת המבחן מול חומר הלימוד ו-Sefaria, ולאחר מכן הזיני תשובות תלמיד/ה לציון.'
        if rtl else
        'Review the current draft against curriculum and Sefaria, then enter student answers for grading.'
    )

    # A teacher can check either the current in-app draft OR upload an existing test file.
    st.markdown('### ' + ('העלי מבחן לבדיקה' if rtl else 'Upload a Test to Check'))
    checker_upload = st.file_uploader(
        'בחרי קובץ מבחן' if rtl else 'Choose a test file',
        type=['pdf', 'docx', 'txt', 'md', 'png', 'jpg', 'jpeg', 'webp'],
        accept_multiple_files=False,
        key='checker_test_upload',
        help=(
            'העלי PDF, Word או קובץ טקסט. הבודק יקרא את השאלות מהקובץ ויבדוק אותן.'
            if rtl else
            'Upload Word, PDF, scanned PDF, JPG/PNG, or text. The Checker will read the test and review/grade it.'
        )
    )

    test_id = st.text_input('מזהה מבחן (Test ID)' if rtl else 'Test ID', key='checker_test_id', help=('הזיני את המזהה הפנימי כדי לחבר אוטומטית למפתח התשובות הנכון.' if rtl else 'Enter the internal ID to connect this upload to the correct saved answer guide.'))
    current_test = st.session_state.get('draft', [])
    current_config = st.session_state.get('config', {})
    if test_id.strip():
        linked = load_test_by_uid(test_id.strip())
        if linked:
            current_test = linked['test']; current_config = linked['config']
            st.success(('מפתח התשובות של המבחן נטען אוטומטית.' if rtl else 'The saved answer guide for this Test ID was loaded automatically.'))
        else:
            st.warning('לא נמצא Test ID כזה.' if rtl else 'That Test ID was not found.')

    if checker_upload is not None:
        try:
            raw_uploaded_test, structured_uploaded_test = ingest_file(
                checker_upload.getvalue(), checker_upload.name, 'prior_test',
                current_config.get('perek') if current_config else None
            )
            imported_questions = []
            for idx, item in enumerate(structured_uploaded_test.get('style_examples', []) or [], 1):
                prompt = str(item.get('prompt', '') or '').strip()
                if not prompt:
                    continue
                perek_hint = item.get('perek') or (current_config.get('perek') if current_config else None)
                imported_questions.append({
                    'prompt': prompt,
                    'answer': str(item.get('answer', '') or '').strip(),
                    'section': str(item.get('section', '') or '').strip(),
                    'difficulty': int(item.get('difficulty', 5) or 5),
                    'source_ref': '',
                    'sefaria_ref': '',
                    'meforash': '',
                    'perek': perek_hint,
                })
            if imported_questions:
                current_test = imported_questions
                st.session_state['checker_uploaded_test'] = imported_questions
                st.session_state['checker_uploaded_name'] = checker_upload.name
                st.success(
                    (f'המבחן נטען לבדיקה: {checker_upload.name} — {len(imported_questions)} שאלות' if rtl else
                     f'Test loaded for checking: {checker_upload.name} — {len(imported_questions)} questions')
                )
            elif raw_uploaded_test.strip():
                st.warning(
                    'הקובץ הועלה, אבל לא הצלחתי לזהות ממנו שאלות מובנות. ודאי שמפתח ה-AI מוגדר או נסי קובץ Word/PDF ברור.'
                    if rtl else
                    'The file uploaded, but I could not identify structured questions from it. Make sure the AI key is configured or try a clearer Word/PDF file.'
                )
            else:
                st.warning('לא נמצא טקסט קריא בקובץ.' if rtl else 'No readable text was found in the uploaded file.')
        except Exception as e:
            st.error(('לא הצלחתי לקרוא את המבחן: ' if rtl else 'Could not read the uploaded test: ') + str(e))

    if not current_test:
        st.info(
            'העלי מבחן כאן, או צרי/פתחי מבחן באפליקציה, כדי להשתמש בבודק ובציונים.'
            if rtl else
            'Upload a test here, or generate/open a test in the app, to use Checker and Grading.'
        )
    else:
        checker_col, grade_col = st.columns(2, gap='large')
        with checker_col:
            st.markdown('### ' + ('בודק לפני פרסום' if rtl else 'Pre-publish Checker'))
            st.write(('שאלות בטיוטה: ' if rtl else 'Questions in draft: ') + str(len(current_test)))
            if st.button('🔎 הריצי בדיקה' if rtl else '🔎 Run Checker', type='primary', use_container_width=True, key='run_checker'):
                curriculum_for_check = get_curriculum(
                    int(current_config.get('perek', 1)),
                    int(current_config.get('start', 1)),
                    int(current_config.get('end', 1))
                ) if current_config else []
                with st.spinner('בודק מקורות, תשובות ובהירות...' if rtl else 'Checking sources, answers, and clarity...'):
                    base = local_check(current_test, current_config)
                    deep = None
                    if grading_ai_ready():
                        try:
                            deep = ai_check(current_test, current_config, curriculum_for_check)
                        except Exception as e:
                            st.warning(('בדיקת AI לא הושלמה: ' if rtl else 'AI check unavailable: ') + str(e))
                    st.session_state['v11_check_results'] = deep or base
            results = st.session_state.get('v11_check_results', [])
            if results:
                passed = sum(1 for x in results if str(x.get('status','')).lower() in ('pass','passed'))
                st.metric('עברו בדיקה' if rtl else 'Passed', f'{passed}/{len(results)}')
                for row in results:
                    status = row.get('status','')
                    icon = '✅' if str(status).lower() in ('pass','passed') else '⚠️'
                    with st.expander(f"{icon} #{row.get('number')} — {status}"):
                        issues = row.get('issues') or []
                        if issues:
                            for issue in issues:
                                st.write('• ' + str(issue))
                        else:
                            st.write('אין בעיות שנמצאו.' if rtl else 'No issues found.')
                        if row.get('suggested_fix'):
                            st.info(row['suggested_fix'])
                        if row.get('source_ref'):
                            st.caption(row['source_ref'])

        with grade_col:
            st.markdown('### ' + ('ציון מבחן' if rtl else 'Grade a Test'))
            st.caption(
                'הדביקי תשובות כמספרים 1., 2., 3. וכו׳. בדיקת AI נותנת גם ניקוד חלקי כאשר היא זמינה.'
                if rtl else
                'Paste answers as 1., 2., 3., etc. AI grading can award partial credit when available.'
            )
            student_name = st.text_input('שם התלמיד/ה' if rtl else 'Student name', key='grade_student_name')
            answer_text = st.text_area('תשובות התלמיד/ה' if rtl else 'Student answers', height=260, key='student_answers_text')
            if st.button('📝 תני ציון' if rtl else '📝 Grade Test', type='primary', use_container_width=True, key='run_grade'):
                answers = parse_student_answers(answer_text, len(current_test))
                with st.spinner('בודק תשובות...' if rtl else 'Grading answers...'):
                    graded = None
                    if grading_ai_ready():
                        try:
                            graded = ai_grade(current_test, answers)
                        except Exception as e:
                            st.warning(('ציון AI לא הושלם: ' if rtl else 'AI grading unavailable: ') + str(e))
                    if not graded:
                        graded = local_grade(current_test, answers)
                    # Attach display detail even when AI returns only scoring fields.
                    for idx, row in enumerate(graded):
                        if idx < len(current_test):
                            row.setdefault('question', current_test[idx].get('prompt',''))
                            row.setdefault('student_answer', answers[idx])
                            row.setdefault('key_answer', current_test[idx].get('answer',''))
                    st.session_state['v11_grade_results'] = graded
            grades = st.session_state.get('v11_grade_results', [])
            if grades:
                earned = sum(float(x.get('points',0) or 0) for x in grades)
                maximum = sum(float(x.get('max_points',1) or 1) for x in grades) or 1
                pct = round(100 * earned / maximum, 1)
                st.metric(('ציון — ' + student_name) if rtl and student_name else ('Score — ' + student_name if student_name else 'Score'), f'{pct}%')
                for row in grades:
                    with st.expander(f"#{row.get('number')} — {row.get('points',0)}/{row.get('max_points',1)}"):
                        st.write('**' + ('שאלה' if rtl else 'Question') + ':** ' + str(row.get('question','')))
                        st.write('**' + ('תשובת תלמיד/ה' if rtl else 'Student answer') + ':** ' + str(row.get('student_answer','')))
                        st.write('**' + ('מפתח תשובות' if rtl else 'Answer key') + ':** ' + str(row.get('key_answer','')))
                        if row.get('feedback'):
                            st.info(str(row['feedback']))

# ===================== LECTURE / AUDIO CHAVRUSA =====================
if active_page == 'lecture':
    st.subheader('הכנת שיעור — Sefaria + שיחה קולית' if rtl else 'Lecture Prep — Sefaria + Conversational Audio')
    st.caption(
        'המקור עצמו מוצג בנפרד: עברית מ-Sefaria, תרגום אנגלי של Sefaria, ואחר כך הסבר של הסוכן.'
        if rtl else
        'The source stays separate: Sefaria Hebrew, Sefaria English, then the agent’s lecture explanation.'
    )

    # Torah Lecture Agent configuration. The key is kept only in this Streamlit session.
    with st.expander('🤖 סוכן השיעור' if rtl else '🤖 Torah Lecture Agent', expanded=True):
        st.write('הסוכן יכול לדבר בקול, לקרוא את המקור, להסביר אותו ולענות על שאלות המשך.' if rtl else 'The agent can speak aloud, read the source, explain it, and answer follow-up questions.')
        agent_key = st.text_input(
            'OpenAI API key — נשמר רק בזמן שהאפליקציה פתוחה' if rtl else 'OpenAI API key — kept only for this app session',
            type='password', key='lecture_agent_api_key',
            help='Needed for open-ended conversation and microphone transcription. Audio reading still has a local Mac fallback.'
        )
        agent_model = st.text_input('מודל הסוכן' if rtl else 'Agent model', value='gpt-4.1-mini', key='lecture_agent_model')
        if agent_key:
            os.environ['OPENAI_API_KEY'] = agent_key
        if lecture_ai_ready(agent_key):
            st.success('הסוכן מחובר ומוכן לשיחה.' if rtl else 'Agent connected and ready for conversation.')
        else:
            st.info('מצב קולי בסיסי עובד גם בלי מפתח API. לשיחה חופשית ולתמלול מיקרופון, הוסיפי מפתח API.' if rtl else 'Basic spoken source mode works without an API key. Add an API key for open-ended conversation and microphone transcription.')

    lecture_mode = st.radio(
        'מצב הכנה' if rtl else 'Preparation mode',
        ['free','notes'],
        format_func=lambda x: ('מקור חופשי' if rtl else 'Any source/topic') if x=='free' else ('מתוך ההערות שלי' if rtl else 'Prepare from my notes'),
        horizontal=True,
        key='lecture_mode'
    )
    l1, l2 = st.columns([1, 1.35], gap='large')
    with l1:
        perek_l = st.selectbox('פרק' if rtl else 'Chapter', list(range(1,41)), index=2, key='lecture_perek')
        if lecture_mode == 'notes':
            max_l = shemot_chapter_lengths()[int(perek_l)-1]
            start_l = st.number_input('פסוק התחלה' if rtl else 'Starting verse', 1, max_l, 1, key='lecture_start')
            end_l = st.number_input('פסוק סיום' if rtl else 'Ending verse', int(start_l), max_l, max(int(start_l), min(max_l, int(start_l)+5)), key='lecture_end')
            note_sources = [x for x in list_sources('notes') if int(x.get('perek') or -1) == int(perek_l)]
            if note_sources:
                selected_note_id = st.selectbox('בחרי קובץ הערות' if rtl else 'Choose a notes file', [x['id'] for x in note_sources], format_func=lambda sid: next((x['name'] for x in note_sources if x['id']==sid), str(sid)), key='lecture_note_source')
                if st.button('🔎 נתחי את ההערות' if rtl else '🔎 Analyze Notes', type='primary', use_container_width=True, key='analyze_notes'):
                    items = get_curriculum(int(perek_l), int(start_l), int(end_l), source_ids=[selected_note_id])
                    plan = notes_lecture_plan(items, int(perek_l), int(start_l), int(end_l), api_key=agent_key, model=agent_model)
                    st.session_state['lecture_notes_plan'] = plan
            else:
                st.info('אין עדיין קובצי הערות שמורים.' if rtl else 'No saved notes files yet.')
        else:
            pasuk_l = st.number_input('פסוק' if rtl else 'Verse', 1, 60, 1, key='lecture_pasuk')
            meforash_l = st.selectbox('מקור' if rtl else 'Source', ['Ramban','Rashi','Sforno','Daas Zekenim','Or HaChaim','Ibn Ezra','Chizkuni','Rabbeinu Bahya','Pasuk'], key='lecture_meforash')
            lecture_ref = f'Exodus {int(perek_l)}:{int(pasuk_l)}' if meforash_l == 'Pasuk' else f'{meforash_l} on Exodus {int(perek_l)}:{int(pasuk_l)}'
            st.code(lecture_ref, language=None)
            if st.button('📚 טעני מקור מ-Sefaria' if rtl else '📚 Load from Sefaria', type='primary', use_container_width=True):
                try:
                    with st.spinner('טוען עברית ואנגלית מ-Sefaria...' if rtl else 'Loading Hebrew and English from Sefaria...'):
                        st.session_state['lecture_source'] = get_bilingual_source(lecture_ref)
                        st.session_state.pop('lecture_explanation', None)
                except Exception as e:
                    st.error(('לא ניתן לטעון את המקור: ' if rtl else 'Could not load source: ') + str(e))

    src = None
    with l2:
        if lecture_mode == 'notes':
            plan = st.session_state.get('lecture_notes_plan', [])
            if plan:
                st.markdown('### ' + ('המפרשים שנמצאו' if rtl else 'Mefarshim found in the selected range'))
                spoken_parts=[]
                for idx,item in enumerate(plan,1):
                    mf=item.get('meforash') or 'Source'; ps=item.get('pasuk') or item.get('pasuk_start')
                    st.write(f"{idx}. **{mf}** — {item.get('topic','')}" + (f" (פסוק {heb_num(ps)})" if rtl and ps else f" (verse {ps})" if ps else ''))
                    if ps and mf and mf.lower() not in ('source','topic'):
                        ref=f'{mf} on Exodus {int(perek_l)}:{int(ps)}'
                        try:
                            bs=get_bilingual_source(ref)
                            spoken_parts.append(f"{mf}. {bs.get('he','')} {bs.get('en','')} {item.get('topic','')} {item.get('details','')}")
                        except Exception:
                            spoken_parts.append(f"{mf}. {item.get('topic','')} {item.get('details','')}")
                    else:
                        spoken_parts.append(f"{mf}. {item.get('topic','')} {item.get('details','')}")
                st.markdown('### ' + ('שמעי את הכנת השיעור' if rtl else 'Listen to the lecture preparation'))
                notes_speech='\n\n'.join(spoken_parts)
                notes_audio=tts_audio_bytes(notes_speech, api_key=agent_key)
                notes_mime='audio/mpeg'
                if not notes_audio:
                    notes_audio=None
                    notes_mime='audio/mpeg'
                speech_player(notes_speech, key='notes_lecture_player_v19', audio_bytes=notes_audio, mime=notes_mime)
            else:
                st.caption('בחרי קובץ וטווח פסוקים ואז לחצי נתחי את ההערות.' if rtl else 'Choose a notes file and pasuk range, then analyze the notes.')
        else:
            src = st.session_state.get('lecture_source')
            if src:
                st.link_button('פתחי ב-Sefaria' if rtl else 'Open in Sefaria', src['url'])
                st.markdown('<div class="source-box"><b>עברית — Sefaria</b><div class="source-he">' + (src.get('he') or '—') + '</div></div>', unsafe_allow_html=True)
                st.markdown('<div class="source-box"><b>English — Sefaria</b><div class="source-en">' + (src.get('en') or 'English translation not available for this exact source on Sefaria.') + '</div></div>', unsafe_allow_html=True)
    if src:
        curriculum_l = get_curriculum(int(perek_l), int(pasuk_l), int(pasuk_l))
        followup = st.text_input(
            'מה תרצי שהסוכן יסביר?' if rtl else 'What should the agent explain?',
            value='',
            placeholder='למשל: מה השאלה של הרמב״ן ואיך הוא עונה?' if rtl else 'For example: What is Ramban asking, and how does he answer?',
            key='lecture_followup_text'
        )
        mic = st.audio_input('🎙️ דברי עם הסוכן' if rtl else '🎙️ Talk to the agent', key='lecture_mic')
        if mic and st.button('השתמשי בהקלטה' if rtl else 'Use microphone question', key='transcribe_mic'):
            spoken = transcribe_audio(mic, api_key=agent_key)
            if spoken:
                st.session_state['lecture_spoken_followup'] = spoken
                st.success(('שמעתי: ' if rtl else 'I heard: ') + spoken)
            else:
                st.warning('לא הצלחתי לתמלל את ההקלטה. אפשר לכתוב את השאלה בשדה למעלה.' if rtl else 'I could not transcribe that recording. You can type the question above.')
        request = st.session_state.get('lecture_spoken_followup') or followup
        if st.button('✨ הכיני את הקטע לשיעור' if rtl else '✨ Prepare This Source for My Lecture', type='primary', use_container_width=True, key='prepare_lecture'):
            if lecture_ai_ready(agent_key):
                with st.spinner('מכין הסבר לשיעור...' if rtl else 'Preparing lecture explanation...'):
                    try:
                        st.session_state['lecture_explanation'] = lecture_explanation(
                            src['ref'], src.get('he',''), src.get('en',''),
                            curriculum_context=str(curriculum_l), user_request=request, api_key=agent_key, model=agent_model, history=st.session_state.get('lecture_agent_history', [])
                        )
                    except Exception as e:
                        st.error(str(e))
            else:
                st.session_state['lecture_explanation'] = basic_agent_script(
                    src['ref'], src.get('he',''), src.get('en',''), curriculum_context=str(curriculum_l)
                )
                st.info('הסוכן פועל במצב בסיסי ללא API: הוא יקרא את המקור והתרגום בקול. הוסיפי מפתח API כדי לשוחח איתו בחופשיות.' if rtl else 'The agent is running in basic no-API mode: it will read the source and translation aloud. Add an API key for open-ended conversation.')
        expl = st.session_state.get('lecture_explanation','')
        if expl:
            st.markdown('### ' + ('הסבר הסוכן' if rtl else 'Agent explanation'))
            st.write(expl)
            speech_text = f"{src.get('he','')}\n\n{src.get('en','')}\n\n{expl}"
            # Prefer OpenAI speech when connected; on a Mac, fall back to the built-in `say` voice.
            audio = tts_audio_bytes(speech_text, api_key=agent_key)
            mime = 'audio/mpeg'
            if not audio:
                audio = None
                mime = 'audio/mpeg'
            speech_player(speech_text, key='v19_lecture_agent_player', audio_bytes=audio, mime=mime)
            st.caption('לחיצה על Play מתחילה את הסוכן לדבר; אפשר לעצור, להשהות ולשנות מהירות עד 2×. אפשר גם להקליט או לכתוב שאלה נוספת ולהכין שוב.' if rtl else 'Play starts the agent speaking. Pause, stop, or change speed up to 2×; then record or type another question and prepare again.')


# ===================== SAVED TESTS =====================
if active_page == 'saved':
    st.subheader(TXT['saved_title'])
    saved = list_saved_tests()

    if not saved:
        st.write('עדיין אין מבחנים שמורים.' if rtl else 'No saved tests yet.')

    for s in saved:
        saved_test = load_saved_test(s['id'])
        if not saved_test:
            continue
        c1, c2, c3, c4 = st.columns([4.8, 1, 1.4, 1])
        when = s['created_at'].replace('T',' ')[:16]
        c1.write(f"**{s['name']}**  \n{TXT['created']}: {when}")

        if c2.button(TXT['load'], key='load' + str(s['id'])):
            st.session_state['draft'] = saved_test['test']
            st.session_state['config'] = saved_test['config']
            st.success('נטען למסך יצירת המבחן.' if rtl else 'Loaded into Build Test.')

        saved_test_doc = export_test_docx(saved_test['test'], saved_test['config'], s['name'])
        saved_key_doc = export_answer_key_docx(saved_test['test'], saved_test['config'], s['name'])
        c3.download_button(
            '📄 Test',
            saved_test_doc.read_bytes(),
            file_name=f"{s['name']} - Test.docx",
            mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            key='download_test_' + str(s['id']),
            use_container_width=True
        )
        st.download_button(
            '🗝️ Answer Key',
            saved_key_doc.read_bytes(),
            file_name=f"{s['name']} - Answer Key.docx",
            mime='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            key='download_key_' + str(s['id'])
        )

        if c4.button(TXT['delete'], key='del' + str(s['id'])):
            delete_saved_test(s['id'])
            st.rerun()
