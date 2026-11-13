# -*- coding: utf-8 -*-
"""
바이낸스 SOXLUSDT(USDⓈ-M 선물) 3분봉을 상장일부터 지금까지 받아 엑셀/CSV로 저장합니다.

사용법 (Windows):
  1) https://www.python.org 에서 Python 설치 (설치 화면에서 "Add python.exe to PATH" 체크)
  2) 명령 프롬프트(cmd)에서:  pip install requests pandas openpyxl
  3) 이 파일이 있는 폴더에서:  python download_soxl_3m.py
  → 같은 폴더에 SOXL_3m_상장이후.xlsx / .csv 생성

데이터:
  - 어제까지: data.binance.vision 공식 아카이브(하루 단위 zip)
  - 오늘(UTC 0시 이후)분: Binance 선물 API (fapi.binance.com) 로 보충
  - 시각은 한국시간(KST). 거래일 = KST 09:00 ~ 익일 08:57 봉 (= UTC 날짜)
"""
import io, zipfile, datetime as dt, time
import requests, pandas as pd

SYMBOL = "SOXLUSDT"
INTERVAL = "3m"
LISTING = dt.date(2026, 5, 15)          # 상장일 (첫 봉 2026-05-15 23:00 KST)
ARCHIVE = "https://data.binance.vision/data/futures/um/daily/klines/{s}/{i}/{s}-{i}-{d}.zip"
API = "https://fapi.binance.com/fapi/v1/klines"
COLS = ["open_time", "open", "high", "low", "close", "volume", "close_time",
        "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume", "ignore"]


def from_archive(day):
    url = ARCHIVE.format(s=SYMBOL, i=INTERVAL, d=day.isoformat())
    r = requests.get(url, timeout=60)
    if r.status_code == 404:
        return None                      # 아직 아카이브에 안 올라온 날
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        raw = z.read(z.namelist()[0]).decode()
    first = raw.split("\n", 1)[0]
    df = pd.read_csv(io.StringIO(raw), header=0 if first.startswith("open_time") else None)
    df.columns = COLS
    return df


def from_api(start_ms):
    rows = []
    while True:
        r = requests.get(API, params={"symbol": SYMBOL, "interval": INTERVAL,
                                      "startTime": start_ms, "limit": 1500}, timeout=30)
        r.raise_for_status()
        chunk = r.json()
        if not chunk:
            break
        rows += chunk
        start_ms = chunk[-1][0] + 1
        if len(chunk) < 1500:
            break
        time.sleep(0.3)
    return pd.DataFrame(rows, columns=COLS) if rows else None


def main():
    today = dt.datetime.now(dt.timezone.utc).date()
    parts, day = [], LISTING
    while day < today:
        df = from_archive(day)
        print(day, "아카이브" if df is not None else "없음 → API로 보충")
        if df is None:
            break
        parts.append(df)
        day += dt.timedelta(days=1)
    # 아카이브에 없는 날부터 지금까지는 API
    start_ms = int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp() * 1000)
    try:
        api = from_api(start_ms)
        if api is not None:
            parts.append(api)
            print("API로", len(api), "봉 추가")
    except Exception as e:
        print("API 실패(지역 제한 등):", e)

    df = pd.concat(parts, ignore_index=True)
    df = df.drop_duplicates("open_time").sort_values("open_time")
    for c in ["open", "high", "low", "close", "volume", "quote_volume"]:
        df[c] = df[c].astype(float)
    utc = pd.to_datetime(df.open_time.astype("int64"), unit="ms")
    out = pd.DataFrame({
        "거래일(KST 09시 기준)": utc.dt.date,
        "시각(KST)": utc + pd.Timedelta(hours=9),
        "시가": df.open, "고가": df.high, "저가": df.low, "종가": df.close,
        "거래량": df.volume, "거래대금(USDT)": df.quote_volume, "체결수": df["count"].astype(int),
    })
    out.to_csv("SOXL_3m_상장이후.csv", index=False, encoding="utf-8-sig")
    out.to_excel("SOXL_3m_상장이후.xlsx", index=False)
    print(f"완료: {len(out):,}봉, {out['시각(KST)'].min()} ~ {out['시각(KST)'].max()} (KST)")


if __name__ == "__main__":
    main()
