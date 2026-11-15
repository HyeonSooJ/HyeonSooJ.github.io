/* 저장소(아카이브)에 아직 없는 날(어제·오늘)의 봉을, 보는 사람의 브라우저가 바이낸스 선물 API에서 직접 받아온다.
   - GitHub(미국 서버)에서는 바이낸스 API가 막혀 있어(451) 이렇게 브라우저에서 받는다. 한국에서 열면 됨.
   - 받은 데이터는 화면에만 쓰고 저장하지 않는다. 정식 저장은 매일 자동 갱신(아카이브)이 한다.
   - 형식은 data.js와 같게: [첫 봉 위치, [o,h,l,c,v]*n (가격×100 정수)]
     3m = 3분 단위 위치, 1m·5m = 분 단위 위치. 하루 = UTC 날짜 = 한국시간 09:00 ~ 익일 09:00 */
(function () {
  const API = 'https://fapi.binance.com/fapi/v1/klines';
  const MS = { '1m': 60e3, '3m': 180e3, '5m': 300e3 };
  const UNIT = { '1m': 60, '3m': 180, '5m': 60 };
  const DAY = 86400e3;
  const iso = t => new Date(t).toISOString().slice(0, 10);

  function withTimeout(p, ms) {
    return Promise.race([p, new Promise((_, no) => setTimeout(() => no(new Error('시간 초과')), ms))]);
  }
  async function get(url) {
    const r = await withTimeout(fetch(url, { cache: 'no-store' }), 10000);
    if (!r.ok) throw new Error('바이낸스 응답 ' + r.status + (r.status === 451 || r.status === 403 ? ' (이 지역/VPN에서는 막힘)' : ''));
    return r.json();
  }
  // startMs부터 지금까지의 봉 (여러 번 나눠 받기)
  async function range(symbol, iv, startMs) {
    const out = [];
    let t = startMs;
    for (let k = 0; k < 20; k++) {
      const rows = await get(`${API}?symbol=${symbol}&interval=${iv}&startTime=${t}&limit=1500`);
      if (!rows.length) break;
      out.push(...rows);
      const last = rows[rows.length - 1][0];
      if (rows.length < 1500) break;
      t = last + MS[iv];
    }
    return out;
  }
  function group(rows, iv) {
    const days = {};
    for (const r of rows) {
      const d = iso(r[0]);
      (days[d] = days[d] || []).push(r);
    }
    const out = {};
    for (const d in days) {
      const rs = days[d].sort((a, b) => a[0] - b[0]);
      const st = Math.floor((rs[0][0] % DAY) / 1000 / UNIT[iv]);
      const flat = [];
      for (const r of rs) flat.push(Math.round(+r[1] * 100), Math.round(+r[2] * 100), Math.round(+r[3] * 100), Math.round(+r[4] * 100), Math.round(+r[5]));
      out[d] = [st, flat];
    }
    return out;
  }
  /* afterDate(YYYY-MM-DD, 저장소의 마지막 날) 다음 날부터 오늘까지.
     결과: { 'YYYY-MM-DD': { '3m':[st,flat], '1m':..., '5m':... }, ... }  (오늘은 진행 중) */
  async function since(symbol, afterDate, intervals) {
    const start = Date.parse(afterDate + 'T00:00:00Z') + DAY;
    if (start > Date.now()) return {};
    const res = {};
    for (const iv of intervals) {
      const g = group(await range(symbol, iv, start), iv);
      for (const d in g) (res[d] = res[d] || {})[iv] = g[d];
    }
    // 3분봉이 없는 날은 버림
    for (const d in res) if (!res[d]['3m']) delete res[d];
    return res;
  }
  const today = () => iso(Date.now());
  window.LIVE = { since, today, day: (symbol, d, intervals) => since(symbol, iso(Date.parse(d + 'T00:00:00Z') - DAY), intervals).then(r => r[d] || null) };
})();
