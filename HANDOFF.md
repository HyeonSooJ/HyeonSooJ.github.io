# 코인 분봉 차트 사이트 — 세션 인계 노트 (2026-11-14)

## 사이트
- 주소: https://hyeonsooj.github.io/chart/ (`#soxl`, `#koru`로 종목 바로 열기)
- 예전 주소 /soxl/, /koru/ → /chart/ 로 자동 이동 (redirect용 index.html만 있음)
- 루트 index.html은 Mock Invest 사이트로 가는 리다이렉트 — 건드리지 말 것
- 저장소: HyeonSooJ/HyeonSooJ.github.io, GitHub Pages는 main 브랜치에서 배포
  (작업 브랜치에서 커밋 → main에 반영해야 공개됨. 사용자가 main 반영을 허락함)

## 데이터
- 코인: 바이낸스 USDⓈ-M 선물 공식 아카이브(data.binance.vision) 일별 zip
  - SOXLUSDT: 상장 2026-05-15 23:00 KST, KORUUSDT: 상장 2026-06-22 22:54 KST
  - 바이낸스 API(api/fapi.binance.com)는 미국 서버에서 451(지역 제한) → 아카이브만 사용
  - 아카이브는 다음 날 UTC 08:00~13:00(한국 17:00~22:00)쯤 올라옴 → 사이트는 항상 전날까지
- 실제 ETF 시가·종가: Yahoo Finance(query1.finance.yahoo.com), SOXL·KORU 모두 NYSE Arca
- 파일 구조: chart/data/<soxl|koru>/
  - data.js  : `const DAYS=[[날짜, 첫봉순번, [o,h,l,c,v]*n ...]]` 3분봉, 가격×100 정수
  - m1/YYYY-MM.json, m5/YYYY-MM.json : {날짜:[첫봉 '분' 위치, 배열]} 1분봉·5분봉
  - stock.js : `const STOCK={날짜:[시가×100, 종가×100, 개장 3분봉순번, 마감 3분봉순번]}`
  - soxl/SOXL_3m.xlsx : 3분봉 엑셀(2026-11-12까지, 자동 갱신 안 됨)
- 하루 = 한국시간 09:00 ~ 익일 09:00 (= UTC 날짜)
- 봉 간격: 1·3·5분은 바이낸스가 만든 그 간격 파일 그대로, 10분은 5분봉 2개를 묶음
  (1분봉을 묶어 3분봉을 만들면 바이낸스 3분봉과 114개 봉이 0.01~0.47 달라서 이렇게 함)

## 자동 갱신
- .github/workflows/data-update.yml : UTC 08:37~20:37 2시간마다 + 수동 실행(Run workflow)
- .github/scripts/update_data.py <폴더> <코인심볼> <ETF티커> [첫날] (표준 라이브러리만)
  - 예) python .github/scripts/update_data.py chart/data/soxl SOXLUSDT SOXL
  - 새 종목은 끝에 상장일을 주면 처음부터 생성
- GitHub에서 수동 실행 2번 성공(그때는 새 날짜 없음). 실제 데이터 커밋은 11/13분이 처음 → 확인 필요

## 페이지 (chart/index.html 하나)
- 종목 목록은 index.html 안 `const SITES={...}` (종목 추가 = 한 줄 + data 폴더)
- 기능: 최신일 큰 차트 / 봉 1·3·5·10분 / 시간대(예 19:00~20:00, 자정 넘김 가능, 브라우저에 기억)
  / 전체·월별·요일별·기간 모아보기 / 주식 시가(주황)·종가(보라) 점선 체크박스(왼쪽 위 숫자, 선은 캔들 뒤)
  / 사진 저장(1장, 모아보기 한 장, 하루씩 폴더 저장=크롬·엣지, 하루씩 ZIP)
- 파일 이름은 영문(한글은 다운로드 때 깨질 수 있음): 예 KORU_5m_2026-11-12_Thu_1900-2000.png
- 크롬 폴더 저장: 바탕화면·다운로드 폴더 "자체"는 막힘 → 그 안의 새 폴더를 골라야 함

## 기타
- soxl/download_soxl_3m.py : 사용자 PC에서 SOXL 3분봉을 엑셀로 받는 스크립트(작업 브랜치에만 있음)
- 클라우드 환경 "Binance data (HyeonSooJ.github.io)": data.binance.vision, Yahoo 등 허용
- 이전 프로젝트(코스피/코루 엑셀 분석)는 별도 — 그 노트는 사용자가 따로 가지고 있음

## 비슷한 날 찾기 (2026-11-14 추가)
- 사용자가 KORU 3분봉 09:00~09:30 사진을 채팅에 올리면 → 가장 비슷한 과거 날 차트 그림을 채팅에 올려주면 됨
- 도구: tools/pattern/find_similar.py (필요: `pip install matplotlib`, numpy·Pillow)
  - `python tools/pattern/find_similar.py 사진.png --out <스크래치패드>/결과` (SOXL은 `--sym soxl`)
  - 결과: detected.png(사진에서 캔들을 어떻게 읽었는지 — 꼭 눈으로 확인), KORU_match1_<날짜>.png(보낼 그림)
  - 캔들 인식이 틀리면 `--crop x0,y0,x1,y1`, `--skip N`, `--take 10`, `--colors gr|rb`로 조정
  - 비교: 첫 n개 3분봉의 시·고·저·종을 (첫 시가 기준, 최고-최저 폭)으로 나눠 모양만 비교(RMS, 작을수록 비슷)
  - 사진에는 오늘 데이터가 아직 없으니(사이트는 전날까지) 과거 날만 후보가 됨
  - 시험: 사이트 화면 캡처 → 정확히 그 날(차이 0.002), 바이낸스풍 그림 → 그 날 1위
- 먼저 `git pull`로 main 최신 데이터를 받아 두고 실행할 것
