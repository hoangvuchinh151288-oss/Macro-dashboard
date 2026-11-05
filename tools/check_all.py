# -*- coding: utf-8 -*-
"""
Bo kiem tra truoc khi push VN Macro Dashboard.

Tu v5.82 du lieu nam o data.js, index.html chi con render.
Script doc CA HAI file.

Chay:  python3 tools/check_all.py                  (tu bat ky cwd nao)
       python3 tools/check_all.py duong/dan/repo
Exit 0 = du dieu kien push · 1 = co FAIL, KHONG push · 2 = khong tim thay file.
"""
import re, sys, io, os, subprocess, datetime, tempfile

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IDX = os.path.join(ROOT, 'index.html')
DAT = os.path.join(ROOT, 'data.js')
for f in (IDX, DAT):
    if not os.path.isfile(f):
        print('KHONG TIM THAY FILE: %s' % f); sys.exit(2)
TMP = tempfile.mkdtemp(prefix='dashchk_')
html = io.open(IDX, encoding='utf-8').read()
data = io.open(DAT, encoding='utf-8').read()
c = data + '\n' + html          # nguon gop, dung cho cac check quet noi dung
TODAY = datetime.date.today()
fail = []; warn = []
print('index.html %d KB · data.js %d KB' % (len(html) // 1024, len(data) // 1024))

# ---------------------------------------------------------------- [1] SYNTAX
# Phai ghi ra FILE roi node --check. `node --check /dev/stdin` cho ket qua sai.
inline = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', html, re.S)
units = [('data.js', data)] + [('index.html script[%d]' % i, s) for i, s in enumerate(inline) if s.strip()]
for name, src in units:
    fn = os.path.join(TMP, re.sub(r'\W+', '_', name) + '.js')
    io.open(fn, 'w', encoding='utf-8').write(src)
    r = subprocess.run(['node', '--check', fn], capture_output=True, text=True)
    if r.returncode != 0:
        fail.append('[1] SYNTAX %s: %s' % (name, r.stderr.strip()[:300]))
print('[1] Syntax: %d unit, %s' % (len(units), 'FAIL' if any(f.startswith('[1]') for f in fail) else 'OK'))

# --------------------------------------------------------------- [2] RUNTIME
# node --check chi bat cu phap. Da co lan ca trang trang vi tham chieu section da xoa.
mock = '''
global.document={getElementById:()=>({innerHTML:'',appendChild:()=>{},style:{},classList:{add:()=>{},remove:()=>{},toggle:()=>{}},querySelectorAll:()=>[],addEventListener:()=>{}}),
querySelector:()=>null,querySelectorAll:()=>[],createElement:()=>({style:{},classList:{add:()=>{}},appendChild:()=>{},setAttribute:()=>{}}),addEventListener:()=>{},body:{innerHTML:'',appendChild:()=>{}}};
global.window={addEventListener:()=>{},location:{href:''},matchMedia:()=>({matches:false,addEventListener:()=>{}})};
global.alert=()=>{}; global.console=console; global.navigator={userAgent:''};
'''
rt = os.path.join(TMP, 'runtime.js')
io.open(rt, 'w', encoding='utf-8').write(mock + '\n' + data + '\n' + '\n'.join(inline))
r = subprocess.run(['node', rt], capture_output=True, text=True, timeout=60)
if r.returncode != 0: fail.append('[2] RUNTIME: ' + r.stderr.strip()[:500])
print('[2] Runtime render: %s' % ('FAIL' if r.returncode != 0 else 'OK'))

# ------------------------------------------------------- [3] NaN / undefined
for m in re.finditer(r'NaN', c):
    ctx = c[max(0, m.start() - 70):m.start() + 40]
    if 'isNaN' in ctx or 'Number.NaN' in ctx or '!NaN' in ctx: continue
    fail.append('[3] NaN ro ri: ...%s...' % ctx.replace('\n', ' '))
for m in re.finditer(r'(undefined|\[object Object\])', c):
    ctx = c[max(0, m.start() - 60):m.start() + 30]
    if 'typeof' in ctx or '!== undefined' in ctx or '=== undefined' in ctx or 'undefined)' in ctx: continue
    warn.append('[3] %s: ...%s...' % (m.group(1), ctx.replace('\n', ' ')[:110]))
print('[3] NaN/undefined: %d loi, %d canh bao' % (
    len([f for f in fail if f.startswith('[3]')]), len([w for w in warn if w.startswith('[3]')])))

# ------------------------------------------------------ [4] SAI KIEU DU LIEU
NUMFIELDS = ['on','w1','w2','m1','ls_omo','gap_vnd_usd','vcb_mua','vcb_ban','nhnn_tc',
             'tn_lon_6_12t','tn_vua_6_12t','us10y','brent','wti']
for m in re.finditer(r'(\w+):\s*\{[^{}]*?value:\s*"([^"]*)"', data):
    fn, v = m.group(1), m.group(2)
    if re.search(r'[A-Za-zÀ-ỹ]+\s*%(?![\w])', v) and not re.search(r'\d\s*%', v):
        fail.append('[4] KIEU DL: %s value co chu truoc dau %% -> "%s"' % (fn, v[:70]))
    if fn in NUMFIELDS:
        if len(v) > 28 or re.search(r'[A-Za-zÀ-ỹ]{3,}', v.replace('dpt', '').replace('d)', '')):
            fail.append('[4] KIEU DL: %s le ra la SO, value="%s"' % (fn, v[:70]))
print('[4] Kieu du lieu: %s' % ('FAIL' if any(f.startswith('[4]') for f in fail) else 'OK'))

# ------------------------------------------- [5] TIER AGE + nguon cua CORE
# Doc ngay cap nhat va source tu data.js, doc TIER_MAP tu index.html.
i = data.find('const D = {'); start = data.find('{', i); d = 0
for j in range(start, len(data)):
    if data[j] == '{': d += 1
    elif data[j] == '}': d -= 1
    if d == 0: end = j + 1; break
Dtxt = data[start:end]; upd = {}; srcmap = {}
for m in re.finditer(r"\n  (\w+):\s*\{", Dtxt):
    dn = m.group(1); s = m.start(0) + len(m.group(0)) - 1; dd = 0
    for j in range(s, len(Dtxt)):
        if Dtxt[j] == '{': dd += 1
        elif Dtxt[j] == '}': dd -= 1
        if dd == 0: e = j + 1; break
    for mm in re.finditer(r"(\w+):\s*\{([^{}]*?)\}", Dtxt[s:e]):
        inner = mm.group(2)
        dm = re.search(r'updated:\s*"(\d{2}/\d{2}/\d{4})"', inner)
        sm = re.search(r'source:\s*"(\[[A-Z]+\])', inner)
        if dm: upd[dn + '.' + mm.group(1)] = dm.group(1)
        if sm: srcmap[dn + '.' + mm.group(1)] = sm.group(1)
i = html.find('const TIER_MAP'); j = html.find('\n};', i); over = []; core = []
for m in re.finditer(r"(CORE|WEEKLY|MONTHLY|QUARTERLY):\s*\{[^}]*?days:\s*(\d+),\s*fields:\s*\[(.*?)\]", html[i:j], re.S):
    nm, days = m.group(1), int(m.group(2))
    for f in re.findall(r"'([^']+)'", m.group(3)):
        if nm == 'CORE': core.append(f)
        dt = upd.get(f)
        if not dt: over.append((nm, f, 'KHONG KHOP', 999)); continue
        a = (TODAY - datetime.datetime.strptime(dt, '%d/%m/%Y').date()).days
        if a > days: over.append((nm, f, dt, a))
over.sort(key=lambda o: -o[3])
for o in over:
    (fail if o[0] == 'CORE' else warn).append('[5] QUA HAN %s %s (%s, %sd)' % (o[0], o[1], o[2], o[3]))
print('[5] Tier age: %d qua han (%d CORE)' % (len(over), len([o for o in over if o[0] == 'CORE'])))

# Field CORE khong duoc lay tu bao chi tong hop. Nguon tong hop da tung ghi sai
# lai suat Big4 6,60-6,80% trong khi VCB thuc te 3,00/5,40.
for f in core:
    if srcmap.get(f) == '[PRESS]':
        warn.append('[5b] NGUON YEU: CORE %s dang dung [PRESS] — can nguon [OFFICIAL]/[PRIMARY]' % f)
print('[5b] Nguon CORE: %d field dung [PRESS]' % len([w for w in warn if w.startswith('[5b]')]))

# --------------------------------------------------- [6] MAU THUAN CHEO
# Doi chieu FIELD CHUAN voi cac lan nhac CO NHAN o value khac.
# Khong quet note: note chua chuoi lich su hop le -> hang chuc canh bao gia.
def _field_value(dom, fn):
    dm = re.search(r'\n  ' + dom + r':\s*\{', data)
    if not dm: return None
    b0 = data.find('{', dm.start()); dd = 0
    for j in range(b0, len(data)):
        if data[j] == '{': dd += 1
        elif data[j] == '}': dd -= 1
        if dd == 0: e0 = j + 1; break
    blk = data[b0:e0]
    fm = re.search(r'\b' + fn + r':\s*\{', blk)
    if not fm: return None
    b1 = blk.find('{', fm.start()); dd = 0
    for j in range(b1, len(blk)):
        if blk[j] == '{': dd += 1
        elif blk[j] == '}': dd -= 1
        if dd == 0: e1 = j + 1; break
    vm = re.search(r'value:\s*("(?:[^"\\]|\\.)*"|-?[\d.]+)', blk[b1:e1])
    return vm.group(1).strip('"') if vm else None

def _norm(t):
    """Chuan hoa so VN: '.' la phan cach nghin, ',' la thap phan.
    25.637 -> 25637 · 3.880,97 -> 3880,97 · 5.00 -> 5,00 (mot dau cham + 2 so = thap phan)."""
    if t is None: return None
    m = re.search(r'\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:[.,]\d+)?', str(t))
    if not m: return None
    v = m.group(0)
    if re.fullmatch(r'\d+\.\d{1,2}', v): return v.replace('.', ',')   # 5.00 -> 5,00
    return v.replace('.', '')

CANON = [
    ('Brent',      'oil',           'brent',    r'Brent[^0-9]{0,14}(\d{2,3},\d{2})'),
    ('WTI',        'oil',           'wti',      r'WTI[^0-9]{0,14}(\d{2,3},\d{2})'),
    ('TC NHNN',    'fx',            'nhnn_tc',  r'TC NHNN[^0-9]{0,14}(\d{2}\.?\d{3})'),
    ('VCB ban',    'fx',            'vcb_ban',  r'VCB ban[^0-9]{0,14}(\d{2}\.?\d{3})'),
    ('VCB mua',    'fx',            'vcb_mua',  r'VCB mua[^0-9]{0,14}(\d{2}\.?\d{3})'),
    ('O/N',        'yield_curve',   'on',       r'O/N[^0-9]{0,10}(\d,\d{2})'),
    ('TT2 1M',     'yield_curve',   'm1',       r'TT2 1M[^0-9]{0,10}(\d,\d{2})'),
    ('DXY',        'dxy',           'value',    r'DXY[^0-9]{0,12}(\d{2,3},\d{2})'),
    ('Vang TG',    'gold',          'tg_usd',   r'[Vv]ang (?:the gioi|TG)[^0-9]{0,16}(\d\.\d{3},\d{2})'),
    ('LS OMO',     'omo',           'ls_omo',   r'LS OMO[^0-9]{0,12}(\d,\d)'),
    ('US 10Y',     'trump_tracker', 'us10y',    r'US 10Y[^0-9]{0,12}(\d[,.]\d{2})'),
]
# Bo qua value la ban ghi lich su co chu dich: chuoi mui ten, du bao cu giu de doi chieu.
# Dau hieu value KHONG phai so cua chi tieu dang doi chieu, nen bo qua:
#   - ban ghi lich su co chu dinh (→, Chuoi:, SO CU, DU BAO CU...)
#   - value cua DUONG CONG KHAC: USD lien ngan hang cung co nhan 'O/N', '1M' nhu VND.
#     Gap 05/11: irp.thuc_te ghi 'USD ... O/N 3,85' bi bao mau thuan voi yield_curve.on 3,70.
#     Khi them field nhac ky han cua mot duong cong khac, phai co nhan 'USD' trong value.
HIST = ('→', 'DU BAO CU', 'DA LAC HAU', 'giu lai de DOI CHIEU', 'Chuoi:', 'SO CU', 'GHI NHAN MISS',
        'USD LIEN NGAN HANG', 'DUONG CONG USD')
allvals = [v for v in re.findall(r'value:\s*"((?:[^"\\]|\\.)*)"', data)
           if not any(h in v for h in HIST)]
for label, dom, fn, pat in CANON:
    canon = _norm(_field_value(dom, fn))
    if not canon: continue
    bad = set()
    for v in allvals:
        for hit in re.findall(pat, v):
            if _norm(hit) != canon: bad.add(hit)
    if bad:
        warn.append('[6] %s: field chuan %s.%s = %s nhung value khac con nhac %s'
                    % (label, dom, fn, canon, sorted(bad)[:6]))
print('[6] Mau thuan cheo: %d canh bao (%d chi tieu doi chieu)'
      % (len([w for w in warn if w.startswith('[6]')]), len(CANON)))

print('\n' + '=' * 60)
if fail:
    print('*** FAIL (%d) — KHONG DUOC PUSH ***' % len(fail))
    for f in fail[:25]: print(' ', f)
if warn:
    print('--- WARN (%d) ---' % len(warn))
    for w in warn[:30]: print(' ', w)
if not fail: print('>>> PASS — du dieu kien push')
sys.exit(1 if fail else 0)
