
import requests
import re
import unicodedata
from urllib.parse import quote

BASE = 'https://www.sefaria.org'


def normalize_pasuk_hebrew(text):
    """Teacher-facing pasuk format: consonants only, no nekudos/trop.

    Sacred-name house style:
      יהוה -> ה׳
      אלהים/אלוהים -> אלקים
      אל שדי / באל שדי -> קל שקי / בקל שקי
    Do not globally replace the ordinary preposition אל.
    """
    if text is None:
        return ''
    if isinstance(text, list):
        return [normalize_pasuk_hebrew(x) for x in text]
    t = str(text)
    # Remove all Hebrew combining marks (nekudos + cantillation).
    t = ''.join(ch for ch in unicodedata.normalize('NFD', t) if unicodedata.category(ch) != 'Mn')
    t = unicodedata.normalize('NFC', t)
    # Normalize maqaf to a regular space for clean classroom copy.
    t = t.replace('־', ' ')
    # Sacred names after marks are stripped.
    t = re.sub(r'(?<![א-ת])יהוה(?![א-ת])', 'ה׳', t)
    t = re.sub(r'(?<![א-ת])(?:אלהים|אלוהים)(?![א-ת])', 'אלקים', t)
    # Only change אל when it is clearly the Divine Name in the phrase אל שדי.
    t = re.sub(r'(?<![א-ת])אל\s+שדי(?![א-ת])', 'קל שקי', t)
    t = re.sub(r'(?<![א-ת])באל\s+שדי(?![א-ת])', 'בקל שקי', t)
    t = re.sub(r'(?<![א-ת])שדי(?![א-ת])', 'שקי', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

CORE = [
    'Rashi','Ramban','Sforno','Daas Zekenim','Da’at Zekenim',"Da'at Zekenim",
    'Or HaChaim','Ohr HaChaim','Ibn Ezra','Chizkuni','Rabbeinu Bahya','Rabbeinu Bachya'
]

def ref_url(ref):
    if not ref:
        return ''
    return f"{BASE}/{quote(ref.replace(' ', '_'), safe=':._-')}"


def get_book_shape(index_title='Exodus'):
    """
    Return the Sefaria shape for a Tanakh book.
    For Tanakh, shape[0]["chapters"] is a list where each item is the
    number of pesukim in that perek.
    """
    r = requests.get(
        f"{BASE}/api/shape/{quote(index_title, safe='')}",
        timeout=20,
    )
    r.raise_for_status()
    data = r.json()
    if not isinstance(data, list) or not data:
        raise ValueError("Unexpected Sefaria Shape API response.")
    return data[0]

def get_chapter_lengths(index_title='Exodus'):
    shape = get_book_shape(index_title)
    chapters = shape.get('chapters') or []
    if not chapters:
        raise ValueError("Sefaria did not return chapter lengths.")
    return [int(x) for x in chapters]

def get_verse_count(chapter, index_title='Exodus'):
    chapter = int(chapter)
    lengths = get_chapter_lengths(index_title)
    if chapter < 1 or chapter > len(lengths):
        raise ValueError(f"Invalid chapter {chapter} for {index_title}.")
    return lengths[chapter - 1]


def get_text(ref, language=None):
    """Fetch a Sefaria text version, explicitly selecting language when requested."""
    params={'return_format':'text_only'}
    if language:
        params['language'] = language
    r = requests.get(
        f"{BASE}/api/v3/texts/{quote(ref, safe='')}",
        params=params,
        timeout=20,
    )
    r.raise_for_status()
    return r.json()

def _version_text(data, lang='he'):
    for v in data.get('versions', []):
        if v.get('language') == lang:
            return v.get('text', '')
    return ''

def get_links(ref):
    r = requests.get(
        f"{BASE}/api/links/{quote(ref, safe='')}",
        params=[('with_text','1'),('category','Commentary')],
        timeout=20,
    )
    r.raise_for_status()
    return r.json()

def _name(link):
    ct = link.get('collectiveTitle') or {}
    candidates = []
    if isinstance(ct, dict):
        candidates += [ct.get('en',''), ct.get('he','')]
    candidates += [link.get('index_title',''), link.get('title','')]
    return ' '.join(x for x in candidates if x)

def get_context(chapter, start, end):
    ref = f'Exodus {chapter}:{start}-{end}'
    out = {
        'base_ref': ref,
        'base_url': ref_url(ref),
        'pesukim': '',
        'verses': {},
        'commentaries': {}
    }
    try:
        base_text = normalize_pasuk_hebrew(_version_text(get_text(ref, 'hebrew'), 'he'))
        out['pesukim'] = base_text
        if isinstance(base_text, list):
            for offset, txt in enumerate(base_text):
                out['verses'][start + offset] = txt
        elif start == end and base_text:
            out['verses'][start] = base_text
    except Exception as e:
        out['base_error'] = str(e)

    # If the range endpoint did not give a verse list, fetch exact verses individually.
    if not out['verses']:
        for pasuk in range(start, end + 1):
            try:
                txt = normalize_pasuk_hebrew(_version_text(get_text(f'Exodus {chapter}:{pasuk}', 'hebrew'), 'he'))
                if isinstance(txt, list):
                    txt = ' '.join(map(str, txt))
                out['verses'][pasuk] = txt
            except Exception:
                pass

    try:
        for link in get_links(ref):
            name = _name(link)
            matched = next((m for m in CORE if m.lower() in name.lower()), None)
            if not matched:
                continue
            source = link.get('sourceRef') or link.get('ref') or ''
            anchor = link.get('anchorRef') or ''
            out['commentaries'].setdefault(matched, []).append({
                'anchor': anchor,
                'source_ref': source,
                'url': ref_url(source),
                'text': link.get('he') or link.get('text') or '',
                'text_en': link.get('en') or '',
            })
    except Exception as e:
        out['links_error'] = str(e)
    return out

def as_prompt_text(ctx, max_chars=24000):
    verse_lines = []
    for pasuk, text in sorted((ctx.get('verses') or {}).items()):
        verse_lines.append(f"Exodus {ctx.get('base_ref','').split()[1].split(':')[0] if ctx.get('base_ref') else ''}:{pasuk}: {text}")
    chunks = ["PESUKIM — EXACT VERSES:\n" + '\n'.join(verse_lines)]
    for name, items in ctx.get('commentaries', {}).items():
        chunks.append(
            name + ':\n' +
            '\n'.join(
                f"ANCHOR {i.get('anchor','')} | SOURCE {i.get('source_ref','')}: {i.get('text','')}"
                for i in items[:30]
            )
        )
    return '\n\n'.join(chunks)[:max_chars]
