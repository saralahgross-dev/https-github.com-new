import base64, json, os, re, subprocess, tempfile
import streamlit.components.v1 as components
from sefaria_client import get_text, ref_url, _version_text


def flatten_text(value):
    if isinstance(value, list):
        return ' '.join(flatten_text(x) for x in value if x)
    return str(value or '').strip()


def get_bilingual_source(ref):
    """Fetch Hebrew and English independently from Sefaria."""
    he_data = get_text(ref, 'hebrew')
    en_data = get_text(ref, 'english')
    return {
        'ref': ref,
        'url': ref_url(ref),
        'he': flatten_text(_version_text(he_data, 'he')),
        'en': flatten_text(_version_text(en_data, 'en')),
    }


def _key(api_key=None):
    return (api_key or os.getenv('OPENAI_API_KEY') or '').strip()


def _model(model=None):
    return (model or os.getenv('OPENAI_MODEL') or 'gpt-4.1-mini').strip()


def ai_ready(api_key=None):
    return bool(_key(api_key))


def tts_audio_bytes(text, api_key=None, voice='alloy'):
    """High quality speech when an OpenAI API key is available."""
    if not _key(api_key) or not text:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=_key(api_key))
        model = os.getenv('OPENAI_TTS_MODEL', 'gpt-4o-mini-tts')
        resp = client.audio.speech.create(
            model=model,
            voice=voice or os.getenv('OPENAI_TTS_VOICE', 'alloy'),
            input=str(text)[:12000],
            response_format='mp3',
        )
        if hasattr(resp, 'read'):
            return resp.read()
        if hasattr(resp, 'content'):
            return resp.content
    except Exception:
        return None
    return None


def mac_tts_audio_bytes(text, rate=1.0):
    """Local Mac fallback. Uses the built-in `say` command and needs no API key."""
    if not text or os.name == 'nt':
        return None
    say = '/usr/bin/say'
    if not os.path.exists(say):
        return None
    path = None
    try:
        fd, path = tempfile.mkstemp(suffix='.aiff')
        os.close(fd)
        wpm = max(90, min(420, int(180 * float(rate or 1.0))))
        subprocess.run([say, '-r', str(wpm), '-o', path, str(text)[:18000]], check=True, timeout=90)
        with open(path, 'rb') as f:
            data = f.read()
        return data or None
    except Exception:
        return None
    finally:
        if path:
            try:
                os.unlink(path)
            except Exception:
                pass


def speech_player(text, key='lecture', height=195, audio_bytes=None, mime='audio/mpeg'):
    """Reliable player: MP3 when available, browser speech as a no-API fallback."""
    element_id = re.sub(r'[^a-zA-Z0-9_-]', '_', key)
    safe_text = json.dumps(str(text or ''))
    audio_html = ''
    if audio_bytes:
        b64 = base64.b64encode(audio_bytes).decode('ascii')
        audio_html = f'<audio id="a_{element_id}" controls preload="auto" style="width:100%"><source src="data:{mime};base64,{b64}" type="{mime}"></audio>'
    components.html(f'''<div style="font-family:Arial;border:1px solid #e6dfd5;border-radius:14px;padding:12px;background:#fffdf8">
      {audio_html}
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px">
        <button onclick="play_{element_id}()">▶ Play</button><button onclick="pause_{element_id}()">⏸ Pause</button><button onclick="resume_{element_id}()">⏯ Resume</button><button onclick="stop_{element_id}()">⏹ Stop</button>
        <label>Speed <select id="rate_{element_id}" onchange="rate_{element_id}()"><option>0.75</option><option selected>1</option><option>1.25</option><option>1.5</option><option>1.75</option><option>2</option></select>×</label>
      </div>
      <div id="status_{element_id}" style="font-size:12px;color:#666;margin-top:6px">Press Play to hear the source.</div>
      <script>
      const t={safe_text}; let u=null; const synth=window.speechSynthesis;
      function browserSpeak_{element_id}() {{ synth.cancel(); u=new SpeechSynthesisUtterance(t); u.rate=parseFloat(document.getElementById('rate_{element_id}').value||'1'); const vs=synth.getVoices(); const hv=vs.find(v=>v.lang&&v.lang.toLowerCase().startsWith('he')); if(hv)u.voice=hv; u.onstart=()=>document.getElementById('status_{element_id}').innerText='Speaking…'; u.onend=()=>document.getElementById('status_{element_id}').innerText='Finished.'; synth.speak(u); }}
      function play_{element_id}() {{ const a=document.getElementById('a_{element_id}'); if(a){{a.playbackRate=parseFloat(document.getElementById('rate_{element_id}').value||'1'); a.play().catch(()=>browserSpeak_{element_id}()); document.getElementById('status_{element_id}').innerText='Playing…';}} else browserSpeak_{element_id}(); }}
      function pause_{element_id}() {{ const a=document.getElementById('a_{element_id}'); if(a&&!a.paused)a.pause(); else synth.pause(); }}
      function resume_{element_id}() {{ const a=document.getElementById('a_{element_id}'); if(a&&a.paused)a.play().catch(()=>browserSpeak_{element_id}()); else synth.resume(); }}
      function stop_{element_id}() {{ const a=document.getElementById('a_{element_id}'); if(a){{a.pause();a.currentTime=0;}} synth.cancel(); document.getElementById('status_{element_id}').innerText='Stopped.'; }}
      function rate_{element_id}() {{ const a=document.getElementById('a_{element_id}'); if(a)a.playbackRate=parseFloat(document.getElementById('rate_{element_id}').value||'1'); if(synth.speaking)browserSpeak_{element_id}(); }}
      </script></div>''', height=height)


def basic_agent_script(ref, he, en, curriculum_context=''):
    """Always-available lecture script. It does not invent content beyond the source supplied."""
    bits = [f'We are learning {ref}.']
    if he:
        bits += ['First, here is the Hebrew source.', he]
    if en:
        bits += ['Now the English translation from Sefaria.', en]
    if curriculum_context:
        bits += ['Your saved curriculum contains related notes for this source. Use the notes on screen together with the source while preparing the lecture.']
    bits += ['You can type a follow-up question below. For open-ended conversational answers, connect the OpenAI agent in this panel.']
    return '\n\n'.join(bits)


def lecture_explanation(ref, he, en, curriculum_context='', user_request='', api_key=None, model=None, history=None):
    if not ai_ready(api_key):
        return basic_agent_script(ref, he, en, curriculum_context)
    from openai import OpenAI
    client = OpenAI(api_key=_key(api_key))
    history = history or []
    prompt = f'''You are the teacher's Torah Lecture Agent and interactive chavrusa.
Use the supplied Sefaria source faithfully. The teacher's curriculum notes are primary for what was taught.
Always distinguish the source itself from your explanation. Never fabricate Torah facts or attribute an idea to a meforash unless supported.
When useful: identify the meforash's question, approach/answer, key words in the Hebrew, and how to teach it clearly.
Respond conversationally so the teacher can keep asking follow-up questions.

SEFARIA REF: {ref}
HEBREW: {he}
ENGLISH: {en}
TEACHER NOTES: {str(curriculum_context)[:18000]}
RECENT CONVERSATION: {json.dumps(history, ensure_ascii=False)[-10000:]}
TEACHER REQUEST: {user_request or 'Prepare this source for my lecture. Read the Hebrew, give the English, and explain it.'}'''
    r = client.responses.create(model=_model(model), input=prompt)
    return r.output_text.strip()


def notes_lecture_plan(items, perek, start, end, api_key=None, model=None):
    if not ai_ready(api_key):
        return [
            {'meforash': x.get('meforash',''), 'topic': x.get('topic',''), 'details': x.get('details',''),
             'perek': x.get('perek'), 'pasuk': x.get('pasuk_start'), 'pasuk_start': x.get('pasuk_start'), 'pasuk_end': x.get('pasuk_end')}
            for x in items if x.get('meforash') or x.get('topic')
        ]
    from openai import OpenAI
    client = OpenAI(api_key=_key(api_key))
    prompt = f'''From these indexed teacher notes, identify the mefarshim actually present and relevant to Shemot {perek}:{start}-{end}.
Match a note to its pasuk not only by literal pasuk words but also by the Rashi and other mefarshim attached to that pasuk. Do not add mefarshim not supported by the notes.
Return JSON list only, each object: meforash, perek, pasuk, topic, confidence, note_basis. If exact pasuk is uncertain, use null and explain in note_basis.
NOTES:\n{json.dumps(items, ensure_ascii=False)[:24000]}'''
    r = client.responses.create(model=_model(model), input=prompt)
    raw = re.sub(r'^```(?:json)?\s*|\s*```$', '', r.output_text.strip(), flags=re.S)
    try:
        return json.loads(raw)
    except Exception:
        return []


def transcribe_audio(audio_file, api_key=None):
    if not _key(api_key) or audio_file is None:
        return ''
    from openai import OpenAI
    client = OpenAI(api_key=_key(api_key))
    model = os.getenv('OPENAI_TRANSCRIBE_MODEL', 'gpt-4o-mini-transcribe')
    data = audio_file.getvalue()
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        f.write(data)
        path = f.name
    try:
        with open(path, 'rb') as af:
            tr = client.audio.transcriptions.create(model=model, file=af)
        return getattr(tr, 'text', '') or ''
    except Exception:
        return ''
    finally:
        try:
            os.unlink(path)
        except Exception:
            pass
