# -*- coding: utf-8 -*-
"""
종목 사이트(soxl/, koru/ …) 데이터 자동 갱신 (GitHub Actions에서 매일 실행, 표준 라이브러리만 사용)

- 바이낸스 공식 아카이브(data.binance.vision)에서 코인 선물 1분·3분·5분봉 하루치 파일을
  사이트에 아직 없는 날부터 '어제(UTC)'까지 받아 data.js / m1/*.json / m5/*.json 에 추가
- Yahoo Finance에서 같은 이름의 ETF 일봉을 받아 stock.js(정규장 시가·종가) 갱신
- 아카이브에 아직 안 올라온 날은 건너뛰고 다음 실행 때 다시 시도
사용: python update_data.py <폴더> <코인심볼> <ETF티커> [첫날]
  예) python .github/scripts/update_data.py soxl SOXLUSDT SOXL
      python .github/scripts/update_data.py koru KORUUSDT KORU 2026-06-22   ← 처음 만들 때는 첫날(상장일)을 줌
"""
import csv, io, json, os, sys, time, zipfile, datetime as dt
import urllib.request, urllib.error
from zoneinfo import ZoneInfo

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else "soxl")
SYMBOL = sys.argv[2] if len(sys.argv) > 2 else "SOXLUSDT"
TICKER = sys.argv[3] if len(sys.argv) > 3 else "SOXL"
FIRST = sys.argv[4] if len(sys.argv) > 4 else None
ARCHIVE = "https://data.binance.vision/data/futures/um/daily/klines/{s}/{i}/{s}-{i}-{d}.zip"
UA = {"User-Agent": "Mozilla/5.0 (soxl-site-updater)"}


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            err = e
        except Exception as e:  # 네트워크 일시 오류
            err = e
        time.sleep(2 * (k + 1))
    raise RuntimeError(f"{url}: {err}")


def klines(interval, day):
    """하루치 봉 → (첫 봉 시작 위치, [o,h,l,c,v]*n 정수배열). 없으면 None"""
    raw = get(ARCHIVE.format(s=SYMBOL, i=interval, d=day))
    if raw is None:
        return None
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        text = z.read(z.namelist()[0]).decode()
    rows = [r for r in csv.reader(io.StringIO(text)) if r and r[0].isdigit()]
    rows.sort(key=lambda r: int(r[0]))
    unit = {"1m": 60, "3m": 180, "5m": 60}[interval]  # 3분봉은 3분 단위 순번, 1·5분봉은 분 단위
    st = (int(rows[0][0]) // 1000 % 86400) // unit
    arr = []
    for r in rows:
        arr += [round(float(r[1]) * 100), round(float(r[2]) * 100), round(float(r[3]) * 100),
                round(float(r[4]) * 100), round(float(r[5]))]
    return st, arr


def load_js(path, prefix, empty, newhead=None):
    if not os.path.exists(path):
        return (newhead or prefix), empty
    s = open(path, encoding="utf-8").read()
    i = s.index(prefix) + len(prefix)
    return s[:i], json.loads(s[i:].strip().rstrip(";"))


def save_js(path, head, obj):
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + json.dumps(obj, separators=(",", ":")) + ";")


def month_file(kind, month):
    p = os.path.join(ROOT, kind, month + ".json")
    return p, (json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {})


def update_candles():
    os.makedirs(ROOT, exist_ok=True)
    head, days = load_js(os.path.join(ROOT, "data.js"), "const DAYS=", [])
    have = {d[0] for d in days}
    if have:
        last = dt.date.fromisoformat(max(have))
    elif FIRST:
        last = dt.date.fromisoformat(FIRST) - dt.timedelta(days=1)
    else:
        sys.exit("data.js가 없습니다. 처음 만들 때는 첫날(상장일)을 네 번째 인자로 주세요.")
    yesterday = dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    added, d = [], last + dt.timedelta(days=1)
    while d <= yesterday:
        ds = d.isoformat()
        k3, k1, k5 = klines("3m", ds), klines("1m", ds), klines("5m", ds)
        if not (k3 and k1 and k5):
            print(ds, "아카이브에 아직 없음 → 다음 실행 때 다시 시도")
            break
        days.append([ds, k3[0], k3[1]])
        for kind, k in (("m1", k1), ("m5", k5)):
            p, obj = month_file(kind, ds[:7])
            obj[ds] = [k[0], k[1]]
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(json.dumps(obj, separators=(",", ":")))
        added.append(ds)
        print(ds, "추가: 3분", len(k3[1]) // 5, "/ 1분", len(k1[1]) // 5, "/ 5분", len(k5[1]) // 5)
        d += dt.timedelta(days=1)
    if added:
        days.sort(key=lambda x: x[0])
        save_js(os.path.join(ROOT, "data.js"), head, days)
    return added, max(x[0] for x in days)


def update_stock(last_day):
    path = os.path.join(ROOT, "stock.js")
    head, stock = load_js(path, "const STOCK=", {}, f"// {TICKER} ETF 정규장 시가·종가 — 출처 Yahoo Finance. [시가*100, 종가*100, 개장 3분봉 순번, 마감 3분봉 순번(KST 09:00 기준)]\nconst STOCK=")
    first_day = load_js(os.path.join(ROOT, "data.js"), "const DAYS=", [])[1][0][0]
    f = dt.date.fromisoformat(first_day) - dt.timedelta(days=10)
    p1 = int(dt.datetime(f.year, f.month, f.day, tzinfo=dt.timezone.utc).timestamp())
    p2 = int(time.time()) + 86400
    raw = None
    for host in ("query1", "query2"):
        try:
            raw = get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{TICKER}?period1={p1}&period2={p2}&interval=1d")
            if raw:
                break
        except Exception as e:
            print("Yahoo 실패:", host, e)
    if not raw:
        print("주가 갱신 건너뜀 (기존 값 유지)")
        return 0
    r = json.loads(raw)["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    ny, n = ZoneInfo("America/New_York"), 0
    for ts, o, c in zip(r["timestamp"], q["open"], q["close"]):
        if o is None or c is None:
            continue
        d = dt.datetime.fromtimestamp(ts, ny).date()
        ds = d.isoformat()
        if ds < first_day or ds > last_day:      # 코인 데이터가 있는 날까지만 (장 마감 끝난 날)
            continue
        base = dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc)
        op = dt.datetime(d.year, d.month, d.day, 9, 30, tzinfo=ny).astimezone(dt.timezone.utc)
        cl = dt.datetime(d.year, d.month, d.day, 16, 0, tzinfo=ny).astimezone(dt.timezone.utc)
        val = [round(o * 100), round(c * 100), int((op - base).total_seconds() // 180), int((cl - base).total_seconds() // 180)]
        if stock.get(ds) != val:
            stock[ds] = val
            n += 1
    stock = dict(sorted(stock.items()))
    save_js(path, head, stock)
    print("주가", n, "일 갱신")
    return n


if __name__ == "__main__":
    added, last = update_candles()
    update_stock(last)
    print("완료. 새로 추가된 날:", added or "없음", "/ 마지막 날:", last)
