import json, os, re
from difflib import SequenceMatcher
from sefaria_client import get_text, _version_text


def ai_ready():
    return bool(os.getenv('OPENAI_API_KEY')) and bool(os.getenv('OPENAI_MODEL'))


def _flatten(x):
    if isinstance(x, list): return ' '.join(_flatten(v) for v in x)
    return str(x or '')


def local_check(test, config):
    rows=[]
    for i,q in enumerate(test,1):
        issues=[]
        ref=q.get('source_ref','')
        if not q.get('prompt','').strip(): issues.append('Missing question text')
        if not q.get('answer','').strip(): issues.append('Missing answer-key answer')
        if not ref: issues.append('Missing exact source pasuk')
        elif not re.match(r'^Exodus\s+\d+:\d+$', ref): issues.append('Source is not one exact Exodus pasuk')
        if q.get('meforash') and not q.get('sefaria_ref'): issues.append('Meforash question is missing commentary reference')
        if not (1 <= int(q.get('difficulty',5) or 5) <= 10): issues.append('Difficulty is outside 1–10')
        rows.append({'number':i,'status':'Needs review' if issues else 'Pass','issues':issues,'source_ref':ref})
    return rows


def ai_check(test, config, curriculum):
    if not ai_ready(): return None
    from openai import OpenAI
    client=OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    source_bundle=[]
    for i,q in enumerate(test,1):
        ref=q.get('sefaria_ref') or q.get('source_ref')
        text=''
        if ref:
            try:
                d=get_text(ref)
                text='HE: '+_flatten(_version_text(d,'he'))+'\nEN: '+_flatten(_version_text(d,'en'))
            except Exception as e:
                text='Sefaria lookup failed: '+str(e)
        source_bundle.append({'number':i,'question':q,'sefaria_text':text[:7000]})
    prompt=f"""Act as a strict Chumash test checker. Return VALID JSON ONLY as a list, one item per question:
{{"number":1,"status":"pass|revise","confidence":0-100,"issues":["..."],"suggested_fix":"..."}}
Check: (1) question is supported by teacher curriculum; (2) exact pasuk/ref is correct; (3) meforash attribution is correct; (4) answer key actually answers the question; (5) no invented untaught content; (6) wording is clear and gradeable.
Notes/PDF curriculum is primary; Sefaria verifies sources, not what was taught.
CONFIG: {json.dumps(config,ensure_ascii=False)}
CURRICULUM: {json.dumps(curriculum,ensure_ascii=False)[:24000]}
QUESTIONS + LIVE SEFARIA TEXT: {json.dumps(source_bundle,ensure_ascii=False)[:50000]}
"""
    r=client.responses.create(model=os.getenv('OPENAI_MODEL'),input=prompt)
    raw=re.sub(r'^```(?:json)?\s*|\s*```$','',r.output_text.strip(),flags=re.S)
    return json.loads(raw)


def parse_student_answers(text, n):
    text=(text or '').strip()
    if not text: return ['']*n
    lines=[x.strip() for x in text.splitlines() if x.strip()]
    out=['']*n
    matched=False
    for line in lines:
        m=re.match(r'^\s*(\d+)\s*[\).:\-]\s*(.*)$',line)
        if m:
            idx=int(m.group(1))-1
            if 0<=idx<n:
                out[idx]=m.group(2).strip(); matched=True
    if not matched:
        for i,line in enumerate(lines[:n]): out[i]=line
    return out


def local_grade(test, student_answers):
    rows=[]
    for i,(q,student) in enumerate(zip(test,student_answers),1):
        key=(q.get('answer') or '').strip()
        ratio=SequenceMatcher(None, key.lower(), (student or '').lower()).ratio() if key and student else 0
        score=1 if ratio>=0.68 else 0
        rows.append({'number':i,'question':q.get('prompt',''),'student_answer':student,'key_answer':key,'points':score,'max_points':1,'feedback':'Correct' if score else 'Review manually'})
    return rows


def ai_grade(test, student_answers):
    if not ai_ready(): return None
    from openai import OpenAI
    client=OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    items=[]
    for i,(q,a) in enumerate(zip(test,student_answers),1):
        items.append({'number':i,'question':q.get('prompt',''),'answer_key':q.get('answer',''),'student_answer':a,'source_ref':q.get('source_ref','')})
    prompt=f"""Grade this Chumash test fairly. Return VALID JSON ONLY as a list:
{{"number":1,"points":0.0,"max_points":1.0,"feedback":"brief teacher feedback"}}
Award partial credit when the student's answer shows meaningful correct understanding. Do not require exact wording. Use the supplied answer key; do not introduce outside requirements.
{json.dumps(items,ensure_ascii=False)[:50000]}
"""
    r=client.responses.create(model=os.getenv('OPENAI_MODEL'), input=prompt)
    raw=re.sub(r'^```(?:json)?\s*|\s*```$','',r.output_text.strip(),flags=re.S)
    return json.loads(raw)
