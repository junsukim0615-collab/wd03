# Week 3 관찰

## Task 1 — 반복 DNS 해석

루트 서버는 `www.korea.ac.kr`의 A 레코드를 관리하지 않으므로 `.kr` NS 위임을 반환한다. RD=0으로 루트부터 직접 따라갔으며, 캡처에서는 루트→`.kr`→`korea.ac.kr`의 3번 질의가 필요했다. 일반적인 클라이언트는 재귀 리졸버에 한 번 질의하고 이 과정을 맡긴다.
glue가 없으면 NS 호스트명을 별도의 루트 기반 조회로 해석하고 그 질의도 path에 합산한다. 이번 고려대 캡처에는 glue가 있어 보조 조회는 0회였고, 이전 Stanford 검증의 총 27회에는 보조 NS 조회와 CNAME 재시작이 포함됐다. 중복 이름·서버 검사, 깊이 30 및 전체 질의 예산 256으로 루프를 막는다.
공식 test_tasks.py에서 5개 이름이 모두 통과했다. 이번 Microsoft는 직접 조회 `104.94.218.45`, dig `23.49.206.40`으로 달랐다. 기존 측정 체인에서 Akamai 도메인을 확인했고 CDN의 시점·리졸버·캐시·부하 분산에 따른 차이와 양립한다. 차이의 단일 원인을 확정하지는 않는다. Task 1은 권한 응답의 질의 이름과 A 레코드를 확인하며 `dig +trace`는 사용하지 않는다.

## Task 2 — 패킷과 steering

기존 자체 캡처 `dns.pcapng`의 1번 질의와 2번 응답은 ID `0xeb20`으로 대응한다. 위임인 2번은 Answer 0/Authority NS 6개이고, 최종 답인 6번은 Answer에 A `163.152.6.10`이 있다. 최대 응답은 2번의 DNS 메시지 341바이트(프레임 383바이트)로, NS 6개와 Additional 10개 때문에 커졌다. 제출 캡처에는 과제 도메인 패킷 6개만 있으며 비공개 원본 캡처는 제외했다.
마지막 두 라벨이 다르면 third-party라는 규칙은 `www.wikipedia.org → dyna.wikimedia.org`를 오판한다. Wikimedia 자체 CDN이므로 도메인 차이가 조직 차이는 아니다. 알려진 Akamai/Fastly/Netlify 도메인을 별도로 확인했고, S3와 CloudFront를 같은 서비스로 취급하지 않는다.
저장된 2026-09-16 학교 Wi-Fi·휴대폰 테더링 자료에서 CDN 서비스 **10개 중 7개**가 resolver 또는 network에 따라 달랐다(리졸버 차이 7/10, 네트워크 차이 3/10). Netflix 홈페이지와 영상 CDN의 차이를 고려해 보조 집계 7/9, 외부 CDN만 7/8도 제시했다. 거점 위치나 RTT를 측정하지 않아 ‘더 가까운 서버’인지는 입증하지 못한다. 9월 30일 단일 네트워크 측정 6/10은 별도 run으로 보존하고 주 집계에 섞지 않았다.

## Task 3 — TTL 캐시와 하한

Baseline의 고정 60초 수명은 짧은 TTL을 넘겨 stale을 만들고, 긴 TTL을 조기에 버려 불필요한 upstream 질의를 만든다. 선형 리스트 탐색도 성능 문제다. 딕셔너리에 실제 `now + ttl` 만료 시각을 저장해 만료 전에만 재사용했으며, TTL=0은 저장하지 않는다.
수정하지 않은 공식 bench의 결과는 baseline 325 upstream/266 stale → YourCache **275 upstream/0 stale**, hit rate 72.5%, simulated time 5.5초였다. 최악의 정확성 사례는 `www.microsoft.com`(TTL 20초)으로 baseline stale 189회이며, CNN은 77회다.
하한은 **275회**다. 빈 캐시에서 각 이름의 최초 질의와 마지막 fetch의 TTL이 지난 뒤 첫 질의는 새 fetch가 필수다. 그 시점까지 fetch를 늦추면 같은 TTL 구간을 가장 멀리 덮으며, 미리 갱신해도 fetch 한 회를 더 소비하므로 더 적은 횟수로 덮지 못한다. 이름별 독립 최소 횟수를 합산했고 구현도 이 하한에 도달했다(고정 TTL, 단일 이름 upstream, 초기 빈 캐시라는 공식 workload 조건).

| 이름 | 최소 upstream |
|---|---:|
| www.microsoft.com | 118 |
| www.cnn.com | 76 |
| www.netflix.com | 37 |
| www.spotify.com | 23 |
| www.github.com | 11 |
| www.wikipedia.org | 6 |
| www.korea.ac.kr | 1 |
| www.stanford.edu | 1 |
| dns.google | 1 |
| a.root-servers.net | 1 |
| 합계 | 275 |

분류 근거: [Wikimedia CDN](https://wikitech.wikimedia.org/wiki/CDN), [Netflix Open Connect](https://openconnect.netflix.com/en/). 전체 체인, 주소 및 패킷 분석은 [report.md](report.md), 재현 벤치 결과는 [bench.txt](bench.txt)에 있다.
