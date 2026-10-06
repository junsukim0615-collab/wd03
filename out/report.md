# Task 2 — DNS capture and steering report

## 측정 환경

학교 Wi-Fi와 휴대폰 테더링의 최신 완료 기록을 선택했다. `현재 네트워크 이름` 기록과 미완료 기록은 제외했다.

- 학교 Wi-Fi: 2026-09-16T05:46:01.174208+00:00 ~ 2026-09-16T05:46:20.954161+00:00 (UTC), run ID `1b2dc676-431d-4746-ba7d-76a6d4653eb8`
- 휴대폰 테더링: 2026-09-16T05:53:47.618996+00:00 ~ 2026-09-16T05:54:13.375249+00:00 (UTC), run ID `95e2c4b7-5ce7-4bfb-b0d8-7b70fcff6ce5`

리졸버: system, Google 8.8.8.8, Quad9 9.9.9.9. 각 네트워크 12개 사이트 × 3개 리졸버의 결과를 검증했다.

## B4. Third-party CDN classification / 제3자 CDN 분류

규칙 R: 원래 이름과 최종 이름의 마지막 두 라벨이 다르면 제3자로 판정한다. 별도로 알려진 CDN 도메인과 운영 주체를 근거로 분류한다. CNAME 부재나 같은 도메인이라는 사실은 CDN 부재를 증명하지 않는다.

최종 zone은 SOA로 검증한 zone cut이 아닌 운영 도메인 표기다. 서로 다른 체인은 모두 표시한다. 제3자 미확인은 부재 확정이 아니다.

| 사이트 | 체인 길이 | 최종 zone | 제3자 여부 / 근거 | 규칙 R 판정 |
|---|---|---|---|---|---|
| www.microsoft.com | 2 | akamaiedge.net | 예 — Akamai | 예 |
| www.netflix.com | 1 | netflix.com | 외부 미확인 — 서비스 단위 자체 CDN | 아니오 |
| www.adobe.com | 2 | akamai.net | 예 — Akamai | 예 |
| www.cnn.com | 1 | fastly.net | 예 — Fastly | 예 |
| www.apple.com | 3 | akamaiedge.net | 예 — Akamai | 예 |
| www.korea.ac.kr | 0 | korea.ac.kr | 외부 CDN 미확인; CDN 집계 제외 | 아니오 |
| www.stanford.edu | 1 | netlifyglobalcdn.com | 예 — Netlify | 예 |
| www.bbc.co.uk | 2 | fastly.net | 예 — Fastly | 예 |
| www.spotify.com | 1 | fastly.net | 예 — Fastly | 예 |
| www.github.com | 1 | github.com | 외부 CDN 미확인; CDN 집계 제외 | 아니오 |
| www.wikipedia.org | 1 | wikimedia.org | 아니오 — Wikimedia 자체 CDN | 예 |
| www.nytimes.com | 3 | fastly.net | 예 — Fastly | 예 |

### 규칙의 실제 오판

Wikipedia의 관측 체인은 `www.wikipedia.org → dyna.wikimedia.org`이다. 규칙 R은 wikipedia.org와 wikimedia.org를 다른 조직으로 오인하여 제3자로 판정한다. 그러나 Wikimedia가 자체 CDN을 운영하므로 거짓 양성이다. 도메인 차이는 운영 조직 차이와 같지 않다. [Wikimedia CDN](https://wikitech.wikimedia.org/wiki/CDN)

마지막 두 라벨은 BBC를 co.uk, 고려대를 ac.kr로 축약하는 한계도 있다. 이번 BBC의 외부 Fastly 판정 자체는 맞으므로 이를 실제 오판 사례로 세지 않는다.

### 분류 근거와 분모

Akamai/Fastly/Netlify 도메인은 외부 CDN 근거로 사용했다. [Akamai](https://techdocs.akamai.com/edge-hostnames/docs/edge-hn-terminology), [Fastly](https://www.fastly.com/documentation/guides/concepts/routing-traffic-to-fastly/), [Netlify](https://answers.netlify.com/t/how-can-i-change-which-netlify-site-my-hostname-is-pointing-to/3259)

Netflix는 과제의 서비스 단위 분류에 따라 자체 CDN 서비스로 포함했다. 다만 www.netflix.com의 DNS 조회는 영상 CDN 경로를 직접 측정한 것이 아니다. [Netflix Open Connect](https://openconnect.netflix.com/en/). GitHub의 주소 변화만으로 CDN이라고 판단하지 않으며, 고려대와 함께 분모에서 제외한다.

## B5. Resolver and network steering 비교

IPv4 주소 집합으로 비교하여 순서와 중복은 무시한다. 같은 네트워크에서 리졸버끼리, 같은 리졸버에서 네트워크끼리 비교한다. 하나라도 차이가 있으면 사이트를 한 번 센다.

| 사이트 | CDN 집계 | 리졸버 차이 | 네트워크 차이 |
|---|---|---|---|
| www.microsoft.com | 포함 | 있음 | 있음 |
| www.netflix.com | 포함 | 없음 | 없음 |
| www.adobe.com | 포함 | 있음 | 있음 |
| www.cnn.com | 포함 | 있음 | 없음 |
| www.apple.com | 포함 | 있음 | 있음 |
| www.korea.ac.kr | 제외 | 없음 | 없음 |
| www.stanford.edu | 포함 | 없음 | 없음 |
| www.bbc.co.uk | 포함 | 있음 | 없음 |
| www.spotify.com | 포함 | 있음 | 없음 |
| www.github.com | 제외 | 있음 | 있음 |
| www.wikipedia.org | 포함 | 없음 | 없음 |
| www.nytimes.com | 포함 | 있음 | 없음 |

**서비스 단위 주 집계: 학교 Wi-Fi와 휴대폰 테더링에서 CDN 사이트 10개 중 7개가 리졸버 또는 네트워크에 따라 달랐다 (7/10).** 리졸버 차이 7/10, 네트워크 차이 3/10.

**Netflix 제외 보조 집계: 학교 Wi-Fi와 휴대폰 테더링에서 CDN 사이트 9개 중 7개가 리졸버 또는 네트워크에 따라 달랐다 (7/9).** 리졸버 차이 7/9, 네트워크 차이 3/9.

**제3자 CDN만 집계: 학교 Wi-Fi와 휴대폰 테더링에서 CDN 사이트 8개 중 7개가 리졸버 또는 네트워크에 따라 달랐다 (7/8).** 리졸버 차이 7/8, 네트워크 차이 3/8.

### 해석과 한계

응답 변화는 확인했지만 ‘더 가까운 복제 서버’라는 주장은 입증하지 못한다. 서버 위치, RTT, HTTP 및 영상 전송을 측정하지 않았다. 두 측정의 시간 차이, 캐시와 부하 분산도 영향을 줄 수 있다. system은 네트워크 변경 시 DNS 서버 자체도 바뀐다. 공개 DNS의 anycast 주소를 물리적 위치로 간주하지 않으며, 같은 IP라고 같은 서버라는 뜻도 아니다. CDN 사용과 주소 변화, 사용자 위치에 따른 선택을 구분해야 한다.

## Part A. 패킷 증거

- 파일: `out/dns.pcapng` (실측 패킷)
- 질의 1번 ↔ 응답 2번: Transaction ID `0xeb20`.
- 위임 응답 2번: Answer 0개, Authority 6개, NS 레코드 존재.
- 최종 답변 6번: Answer 1개, A 주소 `163.152.6.10`.
- 최대 DNS 응답 2번: DNS 메시지 **341바이트**, 프레임 전체 **383바이트**. DNS 길이는 UDP 길이에서 UDP 헤더 8바이트를 뺀 값이다.
- 이 응답에는 Answer 0개, Authority 6개, Additional 10개가 들어 있다. 위임 NS와 추가 주소 레코드가 많은 응답은 최종 A 답변보다 클 수 있다.

기존 Downloads/out의 캡처 로그는 Wi-Fi 인터페이스에서 수집했다고 기록한다. 제출용 파일은 Task 1 패킷만 남긴 파일이며 원본 비공개 캡처는 제출에서 제외한다. pcap과 수집 로그만으로 물리적 장소를 증명할 수는 없다.

## 부록: 관측 CNAME 체인

- `www.microsoft.com`: `www.microsoft.com → www.microsoft.com-c-3.edgekey.net → e13678.dscb.akamaiedge.net`
- `www.netflix.com`: `www.netflix.com → www.prod.ftl.netflix.com`
- `www.adobe.com`: `www.adobe.com → www.adobe.com.edgesuite.net → a1319.dscr.akamai.net`
- `www.cnn.com`: `www.cnn.com → cnn-tls.map.fastly.net`
- `www.apple.com`: `www.apple.com → www-apple-com.v.aaplimg.com → www.apple.com.edgekey.net → e6858.dsce9.akamaiedge.net`
- `www.korea.ac.kr`: `www.korea.ac.kr`
- `www.stanford.edu`: `www.stanford.edu → stanford.netlifyglobalcdn.com`
- `www.bbc.co.uk`: `www.bbc.co.uk → www.bbc.co.uk.pri.bbc.co.uk → bbc.map.fastly.net`
- `www.spotify.com`: `www.spotify.com → atc.spotify.map.fastly.net`
- `www.github.com`: `www.github.com → github.com`
- `www.wikipedia.org`: `www.wikipedia.org → dyna.wikimedia.org`
- `www.nytimes.com`: `www.nytimes.com → www.prd.map.nytimes.com → www.prd.map.nytimes.xovr.nyt.net → nytimes.map.fastly.net`

## 부록: 네트워크·리졸버별 주소 집합

| 네트워크 | 사이트 | 리졸버 | IPv4 주소 집합 | 응답 서버 |
|---|---|---|---|---|
| 학교 Wi-Fi | www.microsoft.com | system | 23.49.206.40 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.microsoft.com | google | 23.49.206.40 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.microsoft.com | quad9 | 184.28.184.92 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.microsoft.com | system | 104.94.218.45 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.microsoft.com | google | 104.94.218.45 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.microsoft.com | quad9 | 23.41.38.100 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.netflix.com | system | 207.45.72.1, 207.45.73.1 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.netflix.com | google | 207.45.72.1, 207.45.73.1 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.netflix.com | quad9 | 207.45.72.1, 207.45.73.1 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.netflix.com | system | 207.45.72.1, 207.45.73.1 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.netflix.com | google | 207.45.72.1, 207.45.73.1 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.netflix.com | quad9 | 207.45.72.1, 207.45.73.1 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.adobe.com | system | 23.76.153.115, 23.76.153.121 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.adobe.com | google | 23.76.153.115, 23.76.153.121 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.adobe.com | quad9 | 23.215.106.160, 23.215.106.161 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.adobe.com | system | 23.32.56.9, 23.32.56.16, 23.32.56.34 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.adobe.com | google | 23.32.56.9, 23.32.56.34 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.adobe.com | quad9 | 23.62.21.75, 23.62.21.82, 23.62.21.101, 23.62.21.110 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.cnn.com | system | 146.75.51.5 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.cnn.com | google | 151.101.3.5, 151.101.67.5, 151.101.131.5, 151.101.195.5 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.cnn.com | quad9 | 151.101.3.5, 151.101.67.5, 151.101.131.5, 151.101.195.5 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.cnn.com | system | 146.75.51.5 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.cnn.com | google | 151.101.3.5, 151.101.67.5, 151.101.131.5, 151.101.195.5 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.cnn.com | quad9 | 151.101.3.5, 151.101.67.5, 151.101.131.5, 151.101.195.5 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.apple.com | system | 23.49.205.28 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.apple.com | google | 23.49.205.28 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.apple.com | quad9 | 23.217.69.53 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.apple.com | system | 104.94.216.37 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.apple.com | google | 23.197.225.61 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.apple.com | quad9 | 23.41.37.53 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.korea.ac.kr | system | 163.152.6.10 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.korea.ac.kr | google | 163.152.6.10 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.korea.ac.kr | quad9 | 163.152.6.10 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.korea.ac.kr | system | 163.152.6.10 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.korea.ac.kr | google | 163.152.6.10 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.korea.ac.kr | quad9 | 163.152.6.10 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.stanford.edu | system | 3.33.186.135, 15.197.167.90 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.stanford.edu | google | 3.33.186.135, 15.197.167.90 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.stanford.edu | quad9 | 3.33.186.135, 15.197.167.90 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.stanford.edu | system | 3.33.186.135, 15.197.167.90 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.stanford.edu | google | 3.33.186.135, 15.197.167.90 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.stanford.edu | quad9 | 3.33.186.135, 15.197.167.90 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.bbc.co.uk | system | 146.75.48.81 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.bbc.co.uk | google | 151.101.0.81, 151.101.64.81, 151.101.128.81, 151.101.192.81 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.bbc.co.uk | quad9 | 151.101.0.81, 151.101.64.81, 151.101.128.81, 151.101.192.81 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.bbc.co.uk | system | 146.75.48.81 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.bbc.co.uk | google | 151.101.0.81, 151.101.64.81, 151.101.128.81, 151.101.192.81 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.bbc.co.uk | quad9 | 151.101.0.81, 151.101.64.81, 151.101.128.81, 151.101.192.81 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.spotify.com | system | 146.75.51.42 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.spotify.com | google | 151.101.3.42, 151.101.67.42, 151.101.131.42, 151.101.195.42 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.spotify.com | quad9 | 151.101.3.42, 151.101.67.42, 151.101.131.42, 151.101.195.42 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.spotify.com | system | 146.75.51.42 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.spotify.com | google | 151.101.3.42, 151.101.67.42, 151.101.131.42, 151.101.195.42 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.spotify.com | quad9 | 151.101.3.42, 151.101.67.42, 151.101.131.42, 151.101.195.42 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.github.com | system | 20.200.245.247 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.github.com | google | 20.200.245.247 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.github.com | quad9 | 20.27.177.113 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.github.com | system | 20.200.245.247 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.github.com | google | 20.200.245.247 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.github.com | quad9 | 20.205.243.166 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.wikipedia.org | system | 103.102.166.224 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.wikipedia.org | google | 103.102.166.224 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.wikipedia.org | quad9 | 103.102.166.224 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.wikipedia.org | system | 103.102.166.224 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.wikipedia.org | google | 103.102.166.224 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.wikipedia.org | quad9 | 103.102.166.224 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 학교 Wi-Fi | www.nytimes.com | system | 146.75.49.164 | 163.152.213.9#53(163.152.213.9) (UDP) |
| 학교 Wi-Fi | www.nytimes.com | google | 151.101.1.164, 151.101.65.164, 151.101.129.164, 151.101.193.164 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 학교 Wi-Fi | www.nytimes.com | quad9 | 151.101.1.164, 151.101.65.164, 151.101.129.164, 151.101.193.164 | 9.9.9.9#53(9.9.9.9) (UDP) |
| 휴대폰 테더링 | www.nytimes.com | system | 146.75.49.164 | 172.20.10.1#53(172.20.10.1) (UDP) |
| 휴대폰 테더링 | www.nytimes.com | google | 151.101.1.164, 151.101.65.164, 151.101.129.164, 151.101.193.164 | 8.8.8.8#53(8.8.8.8) (UDP) |
| 휴대폰 테더링 | www.nytimes.com | quad9 | 151.101.1.164, 151.101.65.164, 151.101.129.164, 151.101.193.164 | 9.9.9.9#53(9.9.9.9) (UDP) |
