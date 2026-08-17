
import json, os, re, random, unicodedata, html
from urllib.parse import quote

SECTION_META = {
    'על מי / על מה נאמר': 'Who / what is this referring to?',
    'לזווג / להתאים': 'Matching',
    'בקשר למה למדנו': 'Connect to what we learned',
    'תרגום / Targum': 'Translation / Targum',
    'שאלת ותשובת רש״י': 'Rashi question & answer',
    'שאלות קצרות': 'Short-answer questions',
    'מפרשים': 'Meforshim',
    'חז״ל / מאמרים': 'Chazal / maamarim',
}

CORE_ORDER = [
    'Rashi', 'Ramban', 'Sforno', 'Daas Zekenim',
    'Ohr HaChaim', 'Ibn Ezra', 'Chizkuni', 'Rabbeinu Bachaye'
]


MEFORASH_ALIASES = {
    'Rashi': ['rashi','רש״י','רשי'],
    'Ramban': ['ramban','רמב״ן','רמבן'],
    'Sforno': ['sforno','ספורנו'],
    'Daas Zekenim': ['daas zekenim','daat zekenim','דעת זקנים'],
    'Ohr HaChaim': ['ohr hachaim','or hachaim','אור החיים'],
    'Ibn Ezra': ['ibn ezra','even ezra','אבן עזרא'],
    'Chizkuni': ['chizkuni','חזקוני'],
    'Rabbeinu Bachaye': ['rabbeinu bachaye','rabbeinu bahya','רבינו בחיי'],
}
HEBREW_MEFORASH = {
    'Rashi':'רש״י', 'Ramban':'רמב״ן', 'Sforno':'ספורנו', 'Daas Zekenim':'דעת זקנים',
    'Ohr HaChaim':'אור החיים', 'Ibn Ezra':'אבן עזרא', 'Chizkuni':'חזקוני', 'Rabbeinu Bachaye':'רבינו בחיי'
}

def _plain_text(text):
    text = html.unescape(str(text or ''))
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    return ' '.join(text.split()).strip()

def _concise_answer(text, max_chars=320):
    """Keep answer boxes clean: no Sefaria HTML/link dumps, usually one concise sentence."""
    text = _plain_text(text)
    if not text:
        return ''
    # Prefer a complete first sentence when the source returned a long commentary dump.
    m = re.search(r'^(.{1,%d}?[.!?׃])(?:\s|$)' % max_chars, text)
    if m:
        return m.group(1).strip()
    if len(text) > max_chars:
        cut = text[:max_chars]
        for sep in [';',' — ',':',',']:
            pos = cut.rfind(sep)
            if pos > max_chars * .55:
                cut = cut[:pos]
                break
        return cut.rstrip(' ,;:-') + '.'
    return text

def _canonical_meforash(text):
    low = _strip_hebrew_marks(text)
    raw = str(text or '').lower()
    for canonical, aliases in MEFORASH_ALIASES.items():
        for alias in aliases:
            if _strip_hebrew_marks(alias) in low or alias.lower() in raw:
                return canonical
    return ''

def allowed_meforshim_from_curriculum(curriculum):
    """Only teacher NOTES (or manually supplied mefarshim) may authorize מפרשים."""
    allowed = set()
    supporting = []
    for item in curriculum or []:
        if item.get('source_type') not in ('notes', 'manual_meforshim'):
            continue
        blob = ' '.join(str(item.get(k) or '') for k in ('meforash','topic','details','source_name'))
        found = _canonical_meforash(blob)
        if found:
            allowed.add(found)
            supporting.append(item)
    return allowed, supporting

def heb_num(n):
    """Hebrew numeral letters for UI/test numbering."""
    try:
        n = int(n)
    except Exception:
        return str(n)
    if n <= 0:
        return str(n)
    if n == 15:
        return 'טו'
    if n == 16:
        return 'טז'
    hundreds = {100:'ק',200:'ר',300:'ש',400:'ת'}
    tens = {10:'י',20:'כ',30:'ל',40:'מ',50:'נ',60:'ס',70:'ע',80:'פ',90:'צ'}
    ones = {1:'א',2:'ב',3:'ג',4:'ד',5:'ה',6:'ו',7:'ז',8:'ח',9:'ט'}
    out = ''
    while n >= 400:
        out += 'ת'; n -= 400
    for value, letter in sorted(hundreds.items(), reverse=True):
        if n >= value:
            out += letter; n -= value
    # 15/16 after removing hundreds
    if n == 15:
        return out + 'טו'
    if n == 16:
        return out + 'טז'
    for value, letter in sorted(tens.items(), reverse=True):
        if n >= value:
            out += letter; n -= value
    if n:
        out += ones.get(n, str(n))
    return out

def heb_label(n, kind=''):
    base = heb_num(n)
    return f"{kind} {base}׳".strip()

def openai_ready():
    return bool(os.getenv('OPENAI_API_KEY')) and bool(os.getenv('OPENAI_MODEL'))

def _json(raw):
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw.strip(), flags=re.S)
    return json.loads(raw)

def sefaria_url(ref):
    if not ref:
        return ''
    return 'https://www.sefaria.org/' + quote(ref.replace(' ', '_'), safe=':._-')

def format_ref(perek, pasuk, language='he'):
    if not perek or not pasuk:
        return ''
    return f"({heb_num(perek)}, {heb_num(pasuk)})" if language == 'he' else f"({perek}:{pasuk})"

def _strip_hebrew_marks(text):
    text = unicodedata.normalize('NFD', str(text or ''))
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    text = re.sub(r'[^א-תA-Za-z0-9\s]', ' ', text)
    return ' '.join(text.split()).lower()

def _pasuk_from_anchor(anchor):
    m = re.search(r'(?:Exodus|Shemot)\s+\d+:(\d+)', str(anchor or ''), flags=re.I)
    return int(m.group(1)) if m else None

def resolve_exact_pasuk(prompt, sefaria_ctx, meforash=''):
    """Resolve a note/question to its base pasuk using pasuk text AND linked mefarshim.

    This intentionally does not require the literal pasuk to appear in teacher notes. A
    Rashi/Ramban/etc. phrase can identify its anchor pasuk through Sefaria's commentary links.
    """
    ctx = sefaria_ctx or {}
    pwords = {_strip_hebrew_marks(prompt).strip()}
    pwords = set(next(iter(pwords), '').split())
    pwords = {w for w in pwords if len(w) >= 2}
    if not pwords:
        return None

    best = (0.0, None)
    # 1) Base pesukim.
    for pasuk, text in (ctx.get('verses') or {}).items():
        vwords = set(_strip_hebrew_marks(text).split())
        overlap = len(pwords & vwords)
        score = overlap / max(1, min(len(pwords), len(vwords))) if vwords else 0
        if overlap >= 2 and score > best[0]:
            best = (score, int(pasuk))

    # 2) Rashi and other mefarshim. This is essential for notes that quote only commentary.
    wanted = str(meforash or '').lower().strip()
    for name, items in (ctx.get('commentaries') or {}).items():
        bonus = 0.12 if wanted and (wanted in name.lower() or name.lower() in wanted) else 0
        for item in items:
            text = ' '.join([str(item.get('text') or ''), str(item.get('text_en') or '')])
            cwords = set(_strip_hebrew_marks(text).split())
            overlap = len(pwords & cwords)
            if not cwords:
                continue
            score = overlap / max(1, min(len(pwords), len(cwords))) + bonus
            pasuk = _pasuk_from_anchor(item.get('anchor')) or _pasuk_from_anchor(item.get('source_ref'))
            if pasuk and overlap >= 2 and score > best[0]:
                best = (score, pasuk)
    return best[1]

def _postprocess(data, config, sefaria_ctx=None):
    language = 'he'
    chapter = int(config['perek'])
    start, end = int(config['start']), int(config['end'])

    cleaned = []
    for q in data:
        perek = int(q.get('perek') or chapter)
        pasuk = q.get('pasuk') or q.get('pasuk_start')
        try:
            pasuk = int(pasuk) if pasuk else None
        except Exception:
            pasuk = None

        # If the model did not return an exact pasuk, try matching the question to the
        # exact selected pasuk text. Never replace it with the whole selected range.
        if not pasuk or not (start <= pasuk <= end):
            pasuk = resolve_exact_pasuk(q.get('prompt', ''), sefaria_ctx, q.get('meforash',''))

        q['perek'] = perek
        q['pasuk'] = pasuk

        if q.get('quotes_pasukan') and pasuk:
            marker = format_ref(perek, pasuk, 'he')
            prompt = q.get('prompt', '').rstrip()
            if marker and marker not in prompt:
                q['prompt'] = f"{prompt} {marker}"

        # DISPLAY SOURCE: exact pasuk only. COMMENTARY LINK: may point to the meforash.
        exact_ref = f"Exodus {perek}:{pasuk}" if pasuk else ''
        commentary_ref = q.get('sefaria_ref') or q.get('commentary_ref') or ''
        model_source_ref = str(q.get('source_ref') or '')
        model_meforash = str(q.get('meforash') or '').strip()

        if ' on Exodus ' in model_source_ref or ' on Shemot ' in model_source_ref:
            commentary_ref = commentary_ref or model_source_ref

        # If the generator named a meforash but failed to provide a commentary ref,
        # construct the most likely exact Sefaria ref from the exact pasuk.
        if model_meforash and pasuk and not commentary_ref:
            name_map = {
                'rashi': 'Rashi',
                'ramban': 'Ramban',
                'sforno': 'Sforno',
                'daas zekenim': 'Daas Zekenim',
                'daat zekenim': 'Daas Zekenim',
                "da'at zekenim": 'Daas Zekenim',
                'ohr hachaim': 'Or HaChaim',
                'or hachaim': 'Or HaChaim',
                'ibn ezra': 'Ibn Ezra',
                'even ezra': 'Ibn Ezra',
                'chizkuni': 'Chizkuni',
                'rabbeinu bachaye': 'Rabbeinu Bahya',
                'rabbeinu bahya': 'Rabbeinu Bahya',
            }
            canonical = name_map.get(model_meforash.lower())
            if canonical:
                commentary_ref = f"{canonical} on Exodus {perek}:{pasuk}"

        q['answer'] = _concise_answer(q.get('answer',''))
        q['answer_en'] = _concise_answer(q.get('answer_en',''))
        q['source_ref'] = exact_ref
        q['sefaria_ref'] = commentary_ref or exact_ref
        q['sefaria_url'] = sefaria_url(q['sefaria_ref'])

        # Keep unsupported questions from claiming a chapter-wide source.
        if not exact_ref:
            q['source_ref'] = ''

        cleaned.append(q)
    return cleaned

def generate_ai(config, curriculum, styles, sefaria_text, recent, mode='notes', sefaria_ctx=None, temporary_sources=None):
    if not openai_ready():
        raise RuntimeError('AI generation is not configured.')

    from openai import OpenAI
    client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    model = os.getenv('OPENAI_MODEL')

    notes = [x for x in curriculum if x.get('source_type') in ('notes','manual_meforshim')]
    allowed_meforshim, meforshim_note_items = allowed_meforshim_from_curriculum(curriculum)
    sheets = [x for x in curriculum if x.get('source_type') != 'notes']
    temporary_sources = temporary_sources or []
    language = 'he'
    test_version = config.get('test_version', 'ivrit_only')
    if test_version == 'ivrit_english':
        language_rule = """The TEST IS ALWAYS HEBREW-FIRST.
For every question, return:
- prompt = Hebrew question only
- prompt_en = faithful English translation of that Hebrew question
- answer = Hebrew gradeable answer
- answer_en = faithful English translation of the answer
Do not create an English-only test.
Every Hebrew question must be natural Hebrew throughout. Translate commentator names too: write אבן עזרא, רמב״ן, ספורנו, רש״י, etc.; never insert English names such as 'Ibn Ezra' inside a Hebrew question."""
    else:
        language_rule = """The TEST IS IVRIT ONLY.
Return Hebrew question text in prompt and Hebrew answer text in answer.
Leave prompt_en and answer_en empty.
Every question must be natural Hebrew throughout. Translate commentator names too: write אבן עזרא, רמב״ן, ספורנו, רש״י, etc.; never insert English names such as 'Ibn Ezra' inside a Hebrew question."""

    if mode == 'existing_tests':
        mode_rules = """
MODE = BASED ON EXISTING TESTS
- Existing tests are the PRIMARY model for wording, section structure, style, and question type.
- Adapt old questions only when they belong to the requested perek/pasuk range.
- PDF notes, any test-specific uploaded worksheet, and Sefaria verify that the concept was actually taught and that the answer/source is correct.
"""
    else:
        mode_rules = """
MODE = NEW QUESTIONS FROM PDF NOTES
- Handwritten/image PDF NOTES are the PRIMARY curriculum map.
- Generate NEW questions from the highlighted headers, fragments, perek/pasuk markers, and main ideas in those notes.
- Existing tests teach style only.
- Printed sheets, a test-specific uploaded worksheet, and Sefaria resolve shorthand and verify context.
"""

    prompt = f"""
Create a Chumash test. Return VALID JSON ONLY: a list of objects in this shape:
{{
  "section":"one requested section",
  "prompt":"Hebrew question text",
  "prompt_en":"English translation only when Ivrit+English is selected, otherwise empty",
  "answer":"Hebrew gradeable answer",
  "answer_en":"English translation only when Ivrit+English is selected, otherwise empty",
  "difficulty":1,
  "source":"short teacher-note/test trace",
  "meforash":"Rashi/Ramban/etc. if relevant",
  "perek":3,
  "pasuk":4,
  "quotes_pasukan":true,
  "source_ref":"Exodus 3:4",
  "sefaria_ref":"Ramban on Exodus 3:4"
}}

{mode_rules}

SOURCE HIERARCHY
1. PDF notes = what was actually taught.
2. Any document uploaded on the Build Test page for THIS test = high-priority contextual source for this test.
3. Previous tests = the teacher's testing style.
4. Printed sheets = fuller context for a topic signaled in the notes.
5. Sefaria = canonical context and verification, not extra curriculum.

PDF NOTE READING RULE
The notes may be handwritten, bilingual Hebrew/English, fragmentary, abbreviated, and visually organized. A page may show only a meforash header, a few words, arrows, and a perek/pasuk marker. Treat that as the highlighted lesson point. Cross-reference the marked perek/pasuk and meforash in Sefaria to understand the shorthand, but TEST ONLY THE HIGHLIGHTED IDEA.

MEFORSHIM PRIORITY
Rashi first; then Ramban, Sforno, Daas Zekenim, Ohr HaChaim, Ibn Ezra, Chizkuni, Rabbeinu Bachaye. Later figures are supplementary only unless the notes explicitly emphasize them.

EXACT PASUK SOURCE RULE — CRITICAL
Every generated question must identify ONE exact base pasuk from the selected range in "perek" and "pasuk".
- Never use the whole selected range as the question source.
- "source_ref" must be the exact base pasuk, e.g. "Exodus 3:4".
- For a meforash question, "sefaria_ref" may be the exact commentary ref, e.g. "Ramban on Exodus 3:4".
- If the Hebrew prompt quotes or nearly quotes even one or two meaningful words from a pasuk, verify the exact pasuk in the supplied Sefaria context, set quotes_pasukan=true, and return its exact perek/pasuk.
- The printed test must show that source once on the HEBREW question line only, in Hebrew-letter form such as (ג, ד).
- In Ivrit + English Translation mode, do NOT repeat the source on the English translation and do NOT print an English numeric source such as (3:4).
- A note does NOT need to quote the pasuk itself. Identify its pasuk by checking, in order: base pasuk text, Rashi on each pasuk, then the other mefarshim linked to those pesukim. Match a quoted/commentary idea back to its anchor pasuk.
- מפרשים IS STRICTLY NOTES-BOUND. The app may invent NEW QUESTION WORDING, but it may NEVER invent/select a meforash that is not present in teacher notes or manually supplied מפרשים material for this range. Prior tests and Sefaria may help with style/verification only; they may NOT authorize a meforash.
- Allowed mefarshim for this request: {sorted(allowed_meforshim)}. If this list is empty, return ZERO מפרשים questions. Do not substitute Rashi or any other commentary merely to fill the requested count.
- If allowed mefarshim exist, generate the requested number of מפרשים questions by mining the note-supported ideas first and then creating additional distinct question angles ONLY from those same note-supported mefarshim/ideas.
- If you cannot identify the exact pasuk with confidence after checking the pasuk and linked mefarshim, do not generate that question.

LANGUAGE
{language_rule}

DIFFICULTY = {config['difficulty']}/10
1-3: direct recall / translation
4-6: straightforward explanation / connection
7-8: synthesis or reasoning within taught material
9-10: discriminating comparison or multi-step reasoning, still only from taught material

REQUESTED RANGE: Shemot {config['perek']}:{config['start']}-{config['end']}
REQUESTED SECTION COUNTS: {json.dumps(config['counts'], ensure_ascii=False)}
TOTAL QUESTIONS: {sum(config['counts'].values())}

TEST-SPECIFIC UPLOADED SOURCES:
{json.dumps(temporary_sources, ensure_ascii=False)[:22000]}

PRIMARY PDF NOTES:
{json.dumps(notes, ensure_ascii=False)[:26000]}

SUPPORTING SHEETS:
{json.dumps(sheets, ensure_ascii=False)[:14000]}

EXISTING TEST EXAMPLES:
{json.dumps(styles, ensure_ascii=False)[:18000]}

SEFARIA CONTEXT:
{sefaria_text[:24000]}

RECENT QUESTIONS TO AVOID REPEATING VERBATIM:
{json.dumps(recent, ensure_ascii=False)[:7000]}

ANSWER BOX RULE: answer must be a clear, concise, gradeable answer in normal language, usually ONE sentence. Never return raw HTML, XML/data tags, a Sefaria URL, or a pasted commentary dump as the answer. Read the source and state the answer.

SOURCE TRACE RULE: First mine/extract question ideas from the teacher notes and prior tests. Keep a short internal source trace in the source field for every question whenever possible. Only after mining those ideas should you create additional grounded formulations to reach the requested count.

Return exactly the requested count per section, EXCEPT מפרשים when no note/manual מפרשים source exists. You MAY and SHOULD invent new question wording, angles, and formulations as needed to reach the count. Do NOT invent Torah facts or unsupported content; every question must remain grounded in the supplied curriculum/Sefaria material.
"""
    # Hard-target generation: requested counts are requirements, not suggestions.
    all_items = []
    missing = dict(config['counts'])
    for attempt in range(8):
        if not any(v > 0 for v in missing.values()):
            break
        attempt_prompt = prompt + "\n\nTHIS PASS MUST SUPPLY THESE STILL-MISSING COUNTS: " + json.dumps(missing, ensure_ascii=False)
        if all_items:
            attempt_prompt += "\nDo not repeat these already-generated prompts: " + json.dumps([x.get('prompt','') for x in all_items], ensure_ascii=False)[:12000]
        response = client.responses.create(model=model, input=attempt_prompt)
        batch = _json(response.output_text)
        if not isinstance(batch, list):
            raise ValueError('Generator did not return a list.')
        batch = _postprocess(batch, config, sefaria_ctx=sefaria_ctx)
        seen = {str(x.get('prompt','')).strip() for x in all_items}
        for x in batch:
            sec = x.get('section')
            if sec not in config['counts'] or not str(x.get('prompt','')).strip() or str(x.get('prompt','')).strip() in seen:
                continue
            if sec == 'מפרשים':
                if not allowed_meforshim:
                    continue
                named = _canonical_meforash(' '.join([str(x.get('meforash') or ''), str(x.get('prompt') or '')]))
                if not named or named not in allowed_meforshim:
                    continue
            current = sum(1 for q in all_items if q.get('section') == sec)
            if current < int(config['counts'][sec]):
                all_items.append(x); seen.add(str(x.get('prompt','')).strip())
        missing = {sec: max(0, int(n)-sum(1 for q in all_items if q.get('section')==sec)) for sec,n in config['counts'].items()}
    return all_items

def generate_local(config, styles, mode='existing_tests', sefaria_ctx=None, curriculum=None, avoid_prompts=None):
    """Offline fallback.

    Requested counts are hard targets. Reuse prior-test style first, then create new
    question formulations from the exact Sefaria pesukim/commentaries. We may make
    up questions; we never make up Torah content.
    """
    rng = random.Random(config.get('seed', 2026))
    avoid = {_strip_hebrew_marks(x) for x in (avoid_prompts or []) if str(x).strip()}
    curriculum = curriculum or []
    allowed_meforshim, meforshim_note_items = allowed_meforshim_from_curriculum(curriculum)
    out = []
    ctx = sefaria_ctx or {}
    verses = [(int(k), v) for k, v in (ctx.get('verses') or {}).items() if v]
    verses.sort()
    commentaries = ctx.get('commentaries') or {}

    def add(section, prompt, answer, pasuk=None, meforash='', source='Sefaria'):
        if _strip_hebrew_marks(prompt) in avoid or any(_strip_hebrew_marks(x.get('prompt','')) == _strip_hebrew_marks(prompt) for x in out):
            return False
        out.append({
            'section': section,
            'prompt': prompt,
            'prompt_en': '',
            'answer': answer,
            'answer_en': '',
            'difficulty': config.get('difficulty', 5),
            'source': source,
            'meforash': meforash,
            'perek': config.get('perek'),
            'pasuk': pasuk,
            'quotes_pasukan': bool(pasuk),
        })
        return True

    for section, count in config['counts'].items():
        target = int(count)
        pool = [x for x in styles if x.get('section') == section and _strip_hebrew_marks(x.get('prompt','')) not in avoid]
        if section == 'מפרשים':
            pool = []  # prior tests may model style, but may not authorize a meforash
        rng.shuffle(pool)
        for x in pool[:target]:
            add(section, x.get('prompt',''), x.get('answer',''), x.get('pasuk') or x.get('pasuk_start'), x.get('meforash',''), x.get('source_name','previous test'))

        have = sum(1 for x in out if x.get('section') == section)
        idx = 0
        while have < target and (verses or commentaries or meforshim_note_items):
            idx += 1
            pasuk, verse = verses[(idx - 1) % len(verses)] if verses else (config.get('start'), '')
            words = str(verse).split()
            excerpt = ' '.join(words[:min(9, len(words))]) if words else f'פסוק {pasuk}'

            if section == 'מפרשים':
                # Strictly notes/manual bound. Sefaria can verify an already-authorized source, never select one.
                if not meforshim_note_items:
                    break
                note = meforshim_note_items[(idx - 1) % len(meforshim_note_items)]
                mf = _canonical_meforash(' '.join([str(note.get('meforash') or ''), str(note.get('topic') or ''), str(note.get('details') or '')]))
                if not mf or mf not in allowed_meforshim:
                    continue
                ps = note.get('pasuk_start') or pasuk
                try: ps = int(ps)
                except Exception: ps = pasuk
                he_mf = HEBREW_MEFORASH.get(mf, mf)
                topic = _plain_text(note.get('topic') or '')
                details = _plain_text(note.get('details') or '')
                templates = [
                    f'לפי {he_mf}, הסבירי את הנקודה שלמדנו על הפסוק ({heb_num(config["perek"])}, {heb_num(ps)}).',
                    f'מה מבאר {he_mf} בפסוק ({heb_num(config["perek"])}, {heb_num(ps)})?',
                    f'לפי {he_mf}, מהו היסוד שלמדנו בעניין {topic or "הפסוק"}?',
                    f'הסבירי בקיצור את דברי {he_mf} שלמדנו על הפסוק ({heb_num(config["perek"])}, {heb_num(ps)}).',
                ]
                prompt = templates[(idx - 1) % len(templates)]
                if _strip_hebrew_marks(prompt) in avoid or any(_strip_hebrew_marks(q.get('prompt','')) == _strip_hebrew_marks(prompt) for q in out):
                    prompt = prompt.rstrip('?') + f' — נקודה {heb_num(idx)}?'
                add(section, prompt, details or topic, ps, mf, note.get('source_name') or 'teacher notes')
            elif section == 'שאלת ותשובת רש״י' and commentaries.get('Rashi'):
                items=commentaries['Rashi']; item=items[(idx-1)%len(items)]
                ps=_pasuk_from_anchor(item.get('anchor')) or _pasuk_from_anchor(item.get('source_ref')) or pasuk
                add(section, f'מה רש״י בא להסביר בפסוק ({heb_num(config["perek"])}, {heb_num(ps)})?', str(item.get('text') or ''), ps, 'Rashi', item.get('source_ref') or 'Sefaria')
            elif section == 'תרגום / Targum':
                add(section, f'תרגמי את לשון הפסוק: ״{excerpt}״.', str(verse), pasuk)
            elif section == 'על מי / על מה נאמר':
                add(section, f'על מי או על מה נאמר בפסוק: ״{excerpt}״?', f'עייני בהקשר של שמות {config["perek"]}:{pasuk}.', pasuk)
            elif section == 'לזווג / להתאים':
                add(section, f'התאימי את הביטוי ״{excerpt}״ לפסוק ולענין המתאים.', f'שמות {config["perek"]}:{pasuk}', pasuk)
            elif section == 'בקשר למה למדנו':
                add(section, f'בקשר למה למדנו את הלשון ״{excerpt}״? הסבירי בקיצור.', str(verse), pasuk)
            elif section == 'חז״ל / מאמרים':
                add(section, f'איזה ענין שלמדנו מתקשר לפסוק ״{excerpt}״?', str(verse), pasuk)
            else:
                add(section, f'הסבירי בקיצור את הפסוק ״{excerpt}״ ואת הענין שלמדנו בו.', str(verse), pasuk)
            have = sum(1 for x in out if x.get('section') == section)

            # Absolute safety valve for an unexpectedly empty context.
            if idx > target * 4:
                break

    return _postprocess(out, config, sefaria_ctx=sefaria_ctx)

