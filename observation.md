# Week 3 — DNS 관찰

## Task 1: 직접 반복 해석

`dig +trace`를 사용하지 않았다. Python 표준 라이브러리의 socket으로 DNS 패킷을 보내며 RD 비트를 0으로 설정했다. 루트에서 시작하여 Authority의 NS 위임과 Additional의 A glue를 따라간다. glue가 없으면 NS 이름을 별도 반복 해석한다. 서버 오류 시 다음 서버를 시도하고, CNAME이면 대상 이름으로 루트부터 다시 시작한다. 최종 A는 질의 이름과 일치하는 권한 응답(AA=1)에서만 채택한다.

R1의 path에는 보조 NS 조회와 실패한 서버 질의 시도도 순서대로 기록한다. R6을 위해 CNAME/NS 재귀 깊이 30, 조회당 전체 질의 예산 256, 이미 방문한 서버 및 진행 중인 이름의 반복 검사를 둔다. UDP 응답이 잘리면 TCP로 재질의한다. IPv4 A 조회용 교육 구현이며 DNSSEC 검증 및 IPv6 전용 NS 지원은 범위 밖이다.

2026-09-30 실행한 `python task1_resolve.py --verify` 결과:

| 이름 | 직접 해석한 A | dig의 A 집합 | hops |
|---|---|---|---:|
| www.korea.ac.kr | 163.152.6.10 | 163.152.6.10 | 3 |
| dns.google | 8.8.8.8 | 8.8.4.4, 8.8.8.8 | 3 |
| en.wikipedia.org | 103.102.166.224 | 103.102.166.224 | 6 |
| www.stanford.edu | 3.33.186.135 | 15.197.167.90, 3.33.186.135 | 27 |
| www.microsoft.com | 104.76.80.143 | 104.76.80.143 | 19 |

결과는 **5/5 ok**였다. 이번 실행에서는 Microsoft도 일치했다. CDN 주소는 시간, 리졸버, 캐시, 부하 분산 정책에 따라 달라질 수 있으므로 다른 실행에서 IP가 달라질 수 있다. 단순한 IP 차이만으로 CDN 동작이라고 확정할 수는 없다. 과제 하네스의 Microsoft 예외는 이를 허용하는 비교 규칙이며, 권한 NS 집합을 비교하는 추가 검증을 구현한 것은 아니다. `dig`는 검증용 비교에만 사용한다.

## Task 2: 측정 방법과 분류 규칙

현재 연결된 한 네트워크에서 2026-09-30 02:40:55–02:41:23 UTC에 측정했다. 물리적 네트워크 종류를 확인하지 않았으므로 `current-network`라고 기록했다. system, Google 8.8.8.8, Quad9 9.9.9.9의 세 리졸버에 12개 사이트를 각각 질의했다. CNAME 연결을 끝까지 기록하고 원래 이름의 IPv4 주소 집합을 비교했다. 36개 사이트/리졸버 조합이 모두 성공했다. 원시 응답, 시각, 응답 서버 및 오류는 [out/chains.json](out/chains.json)에 보존했다. 상세 표와 전체 체인은 [out/report.md](out/report.md)에 있다.

단순 규칙 R은 원래 이름과 최종 이름의 마지막 두 라벨이 다르면 제3자 CDN이라고 판정한다. 이는 검증 대상 휴리스틱이다. 최종 근거 기반 분류는 Akamai, Fastly, Netlify 같은 알려진 서비스 도메인과 운영 주체를 별도로 고려한다. CloudFront의 `cloudfront.net`과 S3를 포함하는 `amazonaws.com`을 같은 CDN 서비스로 묶지 않는다. CNAME이 없거나 도메인이 같다는 사실은 CDN 부재의 증명이 아니다.

### 실제 오판 사례

관측 체인은 `www.wikipedia.org → dyna.wikimedia.org`다. 규칙 R은 두 도메인이 다르므로 제3자라고 오판한다. 그러나 [Wikimedia의 공식 CDN 설명](https://wikitech.wikimedia.org/wiki/CDN)은 Wikimedia 프로젝트용 자체 CDN을 운영함을 설명한다. 따라서 거짓 양성이다. 도메인 문자열 차이와 운영 조직 차이는 같지 않다.

마지막 두 라벨 방식은 BBC를 `co.uk`, 고려대를 `ac.kr`로 축약하는 문제도 있다. 이번 BBC의 실제 최종 이름은 Fastly이므로 이 사례를 실제 오판이라고 주장하지 않는다. 보고서의 final zone은 운영 도메인을 요약한 표기이며 SOA로 확인한 zone cut은 아니다.

### Steering 결과

**6 of 10 sites answered differently to a different resolver.**

과제의 서비스 단위 기준으로 외부 CDN 8개, Wikipedia 자체 CDN, Netflix 자체 CDN 서비스를 포함한 10개 중 6개가 서로 다른 주소 집합을 반환했다. 차이가 난 사이트는 Microsoft, Adobe, CNN, BBC, Spotify, New York Times다. 실패 응답이나 단순한 주소 순서 변화는 차이로 세지 않았다.

Netflix의 [Open Connect](https://openconnect.netflix.com/en/)는 영상 CDN이다. 홈페이지 DNS 측정이 영상 서버 선택을 직접 측정하는 것은 아니므로, Netflix를 제외한 보조 집계는 **6/9**, 제3자 CDN만의 집계는 **6/8**로 구분했다. GitHub와 고려대는 측정에서 CDN 근거가 확인되지 않아 분모에서 제외했으며, 일반적으로 CDN을 사용하지 않는다고 단정하지 않는다.

예를 들어 Microsoft는 system/Google에서 `104.76.80.143`, Quad9에서 `23.63.226.92`였다. 이는 Task 1의 두 조회가 일치한 것과 모순되지 않는다. 서로 다른 조회 조건의 결과이기 때문이다.

### 해석의 한계

주소 차이는 DNS steering과 양립하지만 더 가까운 서버를 선택했다는 증명은 아니다. 공개 DNS의 anycast 주소가 서로 다른 물리적 위치를 보장하지 않고, 순차 질의 사이의 시간·캐시·부하 변화도 영향을 줄 수 있다. 서버 위치, RTT, HTTP/영상 전송은 측정하지 않았다. 같은 IP도 anycast로 다른 거점에 도달할 수 있다. 이번 새 측정에는 네트워크 전환 실험을 포함하지 않았다.

## 재현

Python 3와 `dig`가 필요하다. Windows에서는 PATH의 dig를 우선 사용하고, 없으면 WSL의 dig를 호출한다. Ubuntu/WSL에서는 `sudo apt install dnsutils`로 설치할 수 있다.

```bash
python3 task1_resolve.py --verify
python3 task2_steering.py --collect --network current-network
python3 task2_steering.py --report
```

`--collect`는 기존 JSON의 runs에 새 측정을 추가하고 `--report`는 가장 최근 완료 run을 분석한다. 원본 `test_tasks.py`는 제공받지 못했으므로 해당 통합 채점은 실행하지 않았다.
