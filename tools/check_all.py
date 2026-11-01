# -*- coding: utf-8 -*-
"""
Bo kiem tra truoc khi push VN Macro Dashboard.
Chay:  python3 tools/check_all.py            (tu goc repo)
       python3 tools/check_all.py duong/dan/index.html
Exit 0 = du dieu kien push. Exit 1 = co FAIL, KHONG duoc push.
"""
import re, sys, io, os, subprocess, datetime, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'index.html')
if not os.path.isfile(P):
    print('KHONG TIM THAY FILE: %s' % P); sys.exit(2)
TMP = tempfile.mkdtemp(prefix='dashchk_')
c = io.open(P, encoding='utf-8').read()
TODAY = datetime.date.today()
fail = []; warn = []
print('File: %s (%d KB)' % (P, len(c) // 1024))

# [1] SYNTAX — ghi tung script ra FILE roi node --check (KHONG dung /dev/stdin, cho ket qua sai)
scripts = re.findall(r'<script[^>]*>(.*?)</script>', c, re.S)
for i, s in enumerate(scripts):
    if not s.strip(): continue
    fn = os.path.join(TMP, 'chk_%d.js' % i)
    io.open(fn, 'w', encoding='utf-8').write(s)
    r = subprocess.run(['node', '--check', fn], capture_output=True, text=True)
    if r.returncode != 0:
        fail.append('[1] SYNTAX script[%d]: %s' % (i, r.stderr.strip()[:300]))
print('[1] Syntax: %d script, %s' % (len(scripts), 'FAIL' if any(f.startswith('[1]') for f in fail) else 'OK'))

# [2] RUNTIME — DOM gia lap. node --check chi bat cu phap, khong bat tham chieu section da xoa
mock = '''
global.document={getElementById:()=>({innerHTML:'',appendChild:()=>{},style:{},classList:{add:()=>{},remove:()=>{},toggle:()=>{}},querySelectorAll:()=>[],addEventListener:()=>{}}),
querySelector:()=>null,querySelectorAll:()=>[],createElement:()=>({style:{},classList:{add:()=>{}},appendChild:()=>{},setAttribute:()=>{}}),addEventListener:()=>{},body:{innerHTML:'',appendChild:()=>{}}};
global.window={addEventListener:()=>{},location:{href:''},matchMedia:()=>({matches:false,addEventListener:()=>{}})};
global.alert=()=>{}; global.console=console; global.navigator={userAgent:''};
'''
rt = os.path.join(TMP, 'runtime.js')
io.open(rt, 'w', encoding='utf-8').write(mock + '\n' + '\n'.join(scripts))
r = subprocess.run(['node', rt], capture_output=True, text=True, timeout=60)
if r.returncode != 0: fail.append('[2] RUNTIME: ' + r.stderr.strip()[:500])
print('[2] Runtime render: %s' % ('FAIL' if r.returncode != 0 else 'OK'))

# [3] NaN / undefined ro ri ra HTML
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

# [4] SAI KIEU DU LIEU — chuoi prose nhoi vao field le ra la so
NUMFIELDS = ['on','w1','w2','m1','ls_omo','gap_vnd_usd','vcb_mua','vcb_ban','nhnn_tc',
             'tn_lon_6_12t','tn_vua_6_12t','us10y','brent','wti']
for m in re.finditer(r'(\w+):\s*\{[^{}]*?value:\s*"([^"]*)"', c):
    fn, v = m.group(1), m.group(2)
    if re.search(r'[A-Za-zÀ-ỹ]+\s*%(?![\w])', v) and not re.search(r'\d\s*%', v):
        fail.append('[4] KIEU DL: %s value co chu truoc dau %% -> "%s"' % (fn, v[:70]))
    if fn in NUMFIELDS:
        if len(v) > 28 or re.search(r'[A-Za-zÀ-ỹ]{3,}', v.replace('dpt', '').replace('d)', '')):
            fail.append('[4] KIEU DL: %s le ra la SO, value="%s"' % (fn, v[:70]))
print('[4] Kieu du lieu: %s' % ('FAIL' if any(f.startswith('[4]') for f in fail) else 'OK'))

# [5] TIER AGE — field nao qua nguong tuoi cua tier do
i = c.find('const D = {'); start = c.find('{', i); d = 0
for j in range(start, len(c)):
    if c[j] == '{': d += 1
    elif c[j] == '}': d -= 1
    if d == 0: end = j + 1; break
Dtxt = c[start:end]; upd = {}
for m in re.finditer(r"\n  (\w+):\s*\{", Dtxt):
    dn = m.group(1); s = m.start(0) + len(m.group(0)) - 1; dd = 0
    for j in range(s, len(Dtxt)):
        if Dtxt[j] == '{': dd += 1
        elif Dtxt[j] == '}': dd -= 1
        if dd == 0: e = j + 1; break
    for mm in re.finditer(r"(\w+):\s*\{[^{}]*?updated:\s*\"(\d{2}/\d{2}/\d{4})\"", Dtxt[s:e]):
        upd[dn + '.' + mm.group(1)] = mm.group(2)
i = c.find('const TIER_MAP'); j = c.find('\n};', i); over = []
for m in re.finditer(r"(CORE|WEEKLY|MONTHLY|QUARTERLY):\s*\{[^}]*?days:\s*(\d+),\s*fields:\s*\[(.*?)\]", c[i:j], re.S):
    nm, days = m.group(1), int(m.group(2))
    for f in re.findall(r"'([^']+)'", m.group(3)):
        dt = upd.get(f)
        if not dt: over.append((nm, f, 'KHONG KHOP', 999)); continue
        a = (TODAY - datetime.datetime.strptime(dt, '%d/%m/%Y').date()).days
        if a > days: over.append((nm, f, dt, a))
over.sort(key=lambda o: -o[3])
for o in over:
    (fail if o[0] == 'CORE' else warn).append('[5] QUA HAN %s %s (%s, %sd)' % (o[0], o[1], o[2], o[3]))
print('[5] Tier age: %d qua han (%d CORE)' % (len(over), len([o for o in over if o[0] == 'CORE'])))

# [6] MAU THUAN CHEO — doi chieu FIELD CHUAN voi cac lan nhac CO NHAN o field khac.
#     Bug cu: quet regex so tren toan bo file (ke ca note) -> hang chuc canh bao gia,
#     vi note chua chuoi lich su hop le va vi regex khong biet so do thuoc chi tieu nao.
#     Cach moi: lay gia tri cua field chuan, roi tim trong cac value khac nhung lan
#     nhac CO NHAN ("Brent 109,86"). Lech nhau = mot noi da cap nhat, noi kia chua.
def _field_value(dom, fn):
    dm = re.search(r'\n  ' + dom + r':\s*\{', c)
    if not dm: return None
    b0 = c.find('{', dm.start()); dd = 0
    for j in range(b0, len(c)):
        if c[j] == '{': dd += 1
        elif c[j] == '}': dd -= 1
        if dd == 0: e0 = j + 1; break
    blk = c[b0:e0]
    fm = re.search(r'\b' + fn + r':\s*\{', blk)
    if not fm: return None
    b1 = blk.find('{', fm.start()); dd = 0
    for j in range(b1, len(blk)):
        if blk[j] == '{': dd += 1
        elif blk[j] == '}': dd -= 1
        if dd == 0: e1 = j + 1; break
    vm = re.search(r'value:\s*("(?:[^"\\]|\\.)*"|-?[\d.]+)', blk[b1:e1])
    return vm.group(1).strip('"') if vm else None

def _num(t, thousands=False):
    m = re.search(r'\d{1,3}(?:\.\d{3})+|\d+(?:,\d+)?', t or '')
    if not m: return None
    v = m.group(0)
    return v.replace('.', '') if thousands else v

CANON = [
    ('Brent',   'oil',         'brent',   r'Brent[^0-9]{0,14}(\d{2,3},\d{2})',      False),
    ('TC NHNN', 'fx',          'nhnn_tc', r'TC NHNN[^0-9]{0,14}(\d{2}\.?\d{3})',    True),
    ('VCB ban', 'fx',          'vcb_ban', r'VCB ban[^0-9]{0,14}(\d{2}\.?\d{3})',    True),
    ('O/N',     'yield_curve', 'on',      r'O/N[^0-9]{0,10}(\d,\d{2})',              False),
]
# Bo qua value la BAN GHI LICH SU hop le: chuoi co mui ten, hoac du bao cu duoc
# giu lai de doi chieu. Nhung value nay chua so cu MOT CACH CO CHU DICH, khong phai loi.
HIST = ('→', 'DU BAO CU', 'DA LAC HAU', 'giu lai de DOI CHIEU', 'Chuoi:', 'SO CU')
allvals = [v for v in re.findall(r'value:\s*"((?:[^"\\]|\\.)*)"', c)
           if not any(h in v for h in HIST)]
for label, dom, fn, pat, thou in CANON:
    canon = _num(_field_value(dom, fn), thou)
    if not canon: continue
    bad = set()
    for v in allvals:
        for hit in re.findall(pat, v):
            h = hit.replace('.', '') if thou else hit
            if h != canon: bad.add(hit)
    if bad:
        warn.append('[6] %s: field chuan %s.%s = %s nhung value khac con nhac %s'
                    % (label, dom, fn, canon, sorted(bad)[:6]))
print('[6] Mau thuan cheo: %d canh bao' % len([w for w in warn if w.startswith('[6]')]))

print('\n' + '=' * 60)
if fail:
    print('*** FAIL (%d) — KHONG DUOC PUSH ***' % len(fail))
    for f in fail[:25]: print(' ', f)
if warn:
    print('--- WARN (%d) ---' % len(warn))
    for w in warn[:25]: print(' ', w)
if not fail: print('>>> PASS — du dieu kien push')
sys.exit(1 if fail else 0)
