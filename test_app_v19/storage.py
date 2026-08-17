import json, sqlite3, hashlib, uuid
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent / 'test_app.db'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    sefer TEXT DEFAULT 'Shemot',
    perek INTEGER,
    extracted_text TEXT DEFAULT '',
    metadata_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS curriculum_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    sefer TEXT DEFAULT 'Shemot',
    perek INTEGER,
    pasuk_start INTEGER,
    pasuk_end INTEGER,
    meforash TEXT,
    topic TEXT NOT NULL,
    details TEXT DEFAULT '',
    importance INTEGER DEFAULT 5,
    source_type TEXT NOT NULL,
    FOREIGN KEY(source_id) REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS style_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    section TEXT,
    prompt TEXT NOT NULL,
    answer TEXT DEFAULT '',
    perek INTEGER,
    difficulty INTEGER DEFAULT 5,
    FOREIGN KEY(source_id) REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS saved_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_uid TEXT UNIQUE,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    test_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_uid TEXT NOT NULL,
    student_name TEXT DEFAULT '',
    filename TEXT DEFAULT '',
    grading_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS question_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT UNIQUE,
    prompt TEXT NOT NULL,
    perek INTEGER,
    created_at TEXT NOT NULL
);
'''

def connect():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with connect() as con:
        con.executescript(SCHEMA)
        cols = [r['name'] for r in con.execute('PRAGMA table_info(saved_tests)')]
        if 'test_uid' not in cols:
            con.execute('ALTER TABLE saved_tests ADD COLUMN test_uid TEXT')
        rows = con.execute("SELECT id FROM saved_tests WHERE test_uid IS NULL OR test_uid='' ").fetchall()
        for r in rows:
            con.execute('UPDATE saved_tests SET test_uid=? WHERE id=?', (new_test_uid(), r['id']))
        con.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_saved_tests_uid ON saved_tests(test_uid)')
    try:
        migrate_previous_versions()
    except Exception:
        pass

def migrate_previous_versions():
    """Import persistent data from sibling test_app_v* folders on upgrade.

    The app code may be replaced, but teacher notes/tests must survive. This scans
    sibling version folders (for example test_app_v13/test_app.db) and merges their
    persistent records into the current database without deleting anything.
    """
    current = DB_PATH.resolve()
    parent = DB_PATH.parent.parent
    candidates = []
    for pattern in ('test_app_v*/test_app.db', 'test_app_v*/test_app_v*/test_app.db'):
        candidates.extend(parent.glob(pattern))
    candidates = [x for x in candidates if x.exists() and x.resolve() != current]
    if not candidates:
        return 0
    imported = 0
    with connect() as dst:
        for old in sorted(set(candidates), key=lambda x: x.stat().st_mtime):
            try:
                src = sqlite3.connect(old); src.row_factory = sqlite3.Row
                tables = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                source_map = {}
                if 'sources' in tables:
                    for r in src.execute('SELECT * FROM sources'):
                        rd=dict(r)
                        ex=dst.execute('SELECT id FROM sources WHERE name=? AND source_type=? AND COALESCE(perek,-1)=COALESCE(?,-1) AND extracted_text=?',
                            (rd.get('name',''),rd.get('source_type',''),rd.get('perek'),rd.get('extracted_text',''))).fetchone()
                        if ex: new_id=ex[0]
                        else:
                            cur=dst.execute('INSERT INTO sources(name,source_type,sefer,perek,extracted_text,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)',
                                (rd.get('name',''),rd.get('source_type',''),rd.get('sefer','Shemot'),rd.get('perek'),rd.get('extracted_text',''),rd.get('metadata_json','{}'),rd.get('created_at') or datetime.utcnow().isoformat()))
                            new_id=cur.lastrowid; imported += 1
                        source_map[rd['id']]=new_id
                if 'curriculum_items' in tables:
                    for r in src.execute('SELECT * FROM curriculum_items'):
                        rd=dict(r); sid=source_map.get(rd.get('source_id'))
                        ex=dst.execute('SELECT id FROM curriculum_items WHERE source_id IS ? AND COALESCE(perek,-1)=COALESCE(?,-1) AND COALESCE(pasuk_start,-1)=COALESCE(?,-1) AND COALESCE(pasuk_end,-1)=COALESCE(?,-1) AND meforash=? AND topic=? AND details=?',
                            (sid,rd.get('perek'),rd.get('pasuk_start'),rd.get('pasuk_end'),rd.get('meforash',''),rd.get('topic',''),rd.get('details',''))).fetchone()
                        if not ex:
                            dst.execute('INSERT INTO curriculum_items(source_id,sefer,perek,pasuk_start,pasuk_end,meforash,topic,details,importance,source_type) VALUES(?,?,?,?,?,?,?,?,?,?)',
                                (sid,rd.get('sefer','Shemot'),rd.get('perek'),rd.get('pasuk_start'),rd.get('pasuk_end'),rd.get('meforash',''),rd.get('topic',''),rd.get('details',''),rd.get('importance',5),rd.get('source_type','notes')))
                if 'style_examples' in tables:
                    for r in src.execute('SELECT * FROM style_examples'):
                        rd=dict(r); sid=source_map.get(rd.get('source_id'))
                        ex=dst.execute('SELECT id FROM style_examples WHERE source_id IS ? AND section=? AND prompt=? AND answer=?', (sid,rd.get('section',''),rd.get('prompt',''),rd.get('answer',''))).fetchone()
                        if not ex:
                            dst.execute('INSERT INTO style_examples(source_id,section,prompt,answer,perek,difficulty) VALUES(?,?,?,?,?,?)', (sid,rd.get('section',''),rd.get('prompt',''),rd.get('answer',''),rd.get('perek'),rd.get('difficulty',5)))
                if 'saved_tests' in tables:
                    for r in src.execute('SELECT * FROM saved_tests'):
                        rd=dict(r); uid=rd.get('test_uid') or new_test_uid()
                        if not dst.execute('SELECT 1 FROM saved_tests WHERE test_uid=?',(uid,)).fetchone():
                            dst.execute('INSERT INTO saved_tests(test_uid,name,config_json,test_json,created_at) VALUES(?,?,?,?,?)', (uid,rd.get('name','Imported Test'),rd.get('config_json','{}'),rd.get('test_json','[]'),rd.get('created_at') or datetime.utcnow().isoformat()))
                if 'question_history' in tables:
                    for r in src.execute('SELECT * FROM question_history'):
                        rd=dict(r); dst.execute('INSERT OR IGNORE INTO question_history(fingerprint,prompt,perek,created_at) VALUES(?,?,?,?)',(rd.get('fingerprint'),rd.get('prompt',''),rd.get('perek'),rd.get('created_at') or datetime.utcnow().isoformat()))
                src.close()
            except Exception:
                continue
    return imported

def new_test_uid():
    return 'CT-' + uuid.uuid4().hex[:8].upper()

def add_source(name, source_type, sefer='Shemot', perek=None, extracted_text='', metadata=None):
    with connect() as con:
        cur = con.execute(
            'INSERT INTO sources(name,source_type,sefer,perek,extracted_text,metadata_json,created_at) VALUES(?,?,?,?,?,?,?)',
            (name, source_type, sefer, perek, extracted_text, json.dumps(metadata or {}, ensure_ascii=False), datetime.utcnow().isoformat())
        )
        return cur.lastrowid

def add_curriculum_items(source_id, items, default_type='notes'):
    with connect() as con:
        for x in items:
            if not (x.get('topic') or '').strip():
                continue
            con.execute('''INSERT INTO curriculum_items(source_id,sefer,perek,pasuk_start,pasuk_end,meforash,topic,details,importance,source_type)
                           VALUES(?,?,?,?,?,?,?,?,?,?)''', (
                source_id, x.get('sefer','Shemot'), x.get('perek'), x.get('pasuk_start'), x.get('pasuk_end'),
                x.get('meforash',''), x.get('topic','').strip(), x.get('details','').strip(), int(x.get('importance',5)),
                x.get('source_type', default_type)
            ))

def add_style_examples(source_id, examples):
    with connect() as con:
        for x in examples:
            if not (x.get('prompt') or '').strip():
                continue
            con.execute('''INSERT INTO style_examples(source_id,section,prompt,answer,perek,difficulty)
                           VALUES(?,?,?,?,?,?)''', (
                source_id, x.get('section',''), x.get('prompt','').strip(), x.get('answer','').strip(),
                x.get('perek'), int(x.get('difficulty',5))
            ))

def get_curriculum(perek, start=None, end=None, source_ids=None):
    sql = 'SELECT c.*, s.name AS source_name FROM curriculum_items c LEFT JOIN sources s ON c.source_id=s.id WHERE c.perek=?'
    params = [perek]
    if start is not None and end is not None:
        sql += ' AND (c.pasuk_start IS NULL OR c.pasuk_end IS NULL OR NOT (c.pasuk_end < ? OR c.pasuk_start > ?))'
        params += [start, end]
    if source_ids:
        ph = ','.join('?' for _ in source_ids)
        sql += f' AND c.source_id IN ({ph})'
        params.extend([int(x) for x in source_ids])
    sql += ' ORDER BY c.importance DESC, c.id ASC'
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params)]

def get_style_examples(perek=None, sections=None, limit=80, source_ids=None):
    sql = 'SELECT e.*, s.name AS source_name FROM style_examples e LEFT JOIN sources s ON e.source_id=s.id WHERE 1=1'
    params = []
    if perek is not None:
        sql += ' AND (e.perek=? OR e.perek IS NULL)'
        params.append(perek)
    if sections:
        placeholders = ','.join('?' for _ in sections)
        sql += f' AND e.section IN ({placeholders})'
        params.extend(sections)
    if source_ids:
        ph = ','.join('?' for _ in source_ids)
        sql += f' AND e.source_id IN ({ph})'
        params.extend([int(x) for x in source_ids])
    sql += ' ORDER BY e.id DESC LIMIT ?'
    params.append(limit)
    with connect() as con:
        return [dict(r) for r in con.execute(sql, params)]

def list_sources(source_type=None):
    with connect() as con:
        if source_type:
            return [dict(r) for r in con.execute('SELECT * FROM sources WHERE source_type=? ORDER BY id DESC',(source_type,))]
        return [dict(r) for r in con.execute('SELECT * FROM sources ORDER BY id DESC')]

def source_counts():
    with connect() as con:
        c1 = con.execute('SELECT COUNT(*) FROM curriculum_items').fetchone()[0]
        c2 = con.execute('SELECT COUNT(*) FROM style_examples').fetchone()[0]
        c3 = con.execute('SELECT COUNT(*) FROM sources').fetchone()[0]
        return c3, c1, c2

def save_test(name, config, test, test_uid=None):
    uid = test_uid or config.get('test_uid') or new_test_uid()
    config = dict(config)
    config['test_uid'] = uid
    with connect() as con:
        existing = con.execute('SELECT id FROM saved_tests WHERE test_uid=?',(uid,)).fetchone()
        if existing:
            con.execute('UPDATE saved_tests SET name=?,config_json=?,test_json=? WHERE test_uid=?',
                        (name, json.dumps(config, ensure_ascii=False), json.dumps(test, ensure_ascii=False), uid))
        else:
            con.execute('INSERT INTO saved_tests(test_uid,name,config_json,test_json,created_at) VALUES(?,?,?,?,?)',
                        (uid, name, json.dumps(config, ensure_ascii=False), json.dumps(test, ensure_ascii=False), datetime.utcnow().isoformat()))
    return uid

def list_saved_tests():
    with connect() as con:
        return [dict(r) for r in con.execute('SELECT id,test_uid,name,created_at FROM saved_tests ORDER BY id DESC')]

def load_saved_test(test_id):
    with connect() as con:
        r = con.execute('SELECT * FROM saved_tests WHERE id=?',(test_id,)).fetchone()
        if not r: return None
        return _decode_test_row(r)

def load_test_by_uid(test_uid):
    if not test_uid: return None
    with connect() as con:
        r = con.execute('SELECT * FROM saved_tests WHERE UPPER(test_uid)=UPPER(?)',(test_uid.strip(),)).fetchone()
        return _decode_test_row(r) if r else None

def _decode_test_row(r):
    d = dict(r)
    d['config'] = json.loads(d['config_json'])
    d['test'] = json.loads(d['test_json'])
    return d

def delete_saved_test(test_id):
    with connect() as con:
        con.execute('DELETE FROM saved_tests WHERE id=?',(test_id,))

def save_submission(test_uid, student_name, filename, grading):
    with connect() as con:
        con.execute('INSERT INTO submissions(test_uid,student_name,filename,grading_json,created_at) VALUES(?,?,?,?,?)',
                    (test_uid, student_name or '', filename or '', json.dumps(grading or [], ensure_ascii=False), datetime.utcnow().isoformat()))

def remember_questions(test, perek):
    with connect() as con:
        for q in test:
            prompt = q.get('prompt','').strip()
            if not prompt: continue
            fp = hashlib.sha256(prompt.encode('utf-8')).hexdigest()
            con.execute('INSERT OR IGNORE INTO question_history(fingerprint,prompt,perek,created_at) VALUES(?,?,?,?)',
                        (fp,prompt,perek,datetime.utcnow().isoformat()))

def recent_questions(perek=None, limit=80):
    sql='SELECT prompt FROM question_history'; params=[]
    if perek is not None:
        sql+=' WHERE perek=?'; params.append(perek)
    sql+=' ORDER BY id DESC LIMIT ?'; params.append(limit)
    with connect() as con:
        return [r['prompt'] for r in con.execute(sql,params)]

def rename_source(source_id, new_name):
    new_name = (new_name or '').strip()
    if not new_name: raise ValueError('Source name cannot be blank.')
    with connect() as con:
        existing = con.execute('SELECT id FROM sources WHERE name=? AND id<>?',(new_name, int(source_id))).fetchone()
        if existing:
            base = new_name; i = 2
            while con.execute('SELECT id FROM sources WHERE name=? AND id<>?',(f'{base} ({i})', int(source_id))).fetchone(): i += 1
            new_name = f'{base} ({i})'
        con.execute('UPDATE sources SET name=? WHERE id=?', (new_name, int(source_id)))
    return new_name

def delete_source(source_id):
    source_id = int(source_id)
    with connect() as con:
        con.execute('DELETE FROM curriculum_items WHERE source_id=?',(source_id,))
        con.execute('DELETE FROM style_examples WHERE source_id=?',(source_id,))
        con.execute('DELETE FROM sources WHERE id=?',(source_id,))

def get_source(source_id):
    with connect() as con:
        row = con.execute('SELECT * FROM sources WHERE id=?',(int(source_id),)).fetchone()
        return dict(row) if row else None

init_db()
