# Week 3 — DNS Hierarchy and CDNs

이 저장소의 루트가 강의의 `w03-dns/`에 해당한다. 과제 요구사항은 [강의 README](https://github.com/codingchild2424/2026-lecture-network-practice/blob/main/w03-dns/README.md), [Task 1](https://github.com/codingchild2424/2026-lecture-network-practice/blob/main/w03-dns/task1.md), [Task 2](https://github.com/codingchild2424/2026-lecture-network-practice/blob/main/w03-dns/task2.md), [Task 3](https://github.com/codingchild2424/2026-lecture-network-practice/blob/main/w03-dns/task3.md)를 기준으로 한다.

## 제출 파일

- `task1_resolve.py`: RD=0 반복 DNS 해석, NS/glue/CNAME/서버 실패/루프 처리
- `task2_steering.py`: CNAME 및 resolver별 A 수집, 저장된 학교 Wi-Fi·휴대폰 테더링 비교, tshark 캡처 분석
- `task3_cache.py`: 실제 TTL을 지키는 YourCache
- `bench.py`, `test_tasks.py`: 강의에서 받은 원본 그대로
- `out/dns.pcapng`: 과제 질의만 남긴 자체 캡처
- `out/chains.json`, `out/report.md`: 두 네트워크 원본과 분석
- `out/bench.txt`: 공식 벤치마크 출력
- **[out/observation.md](out/observation.md)**: 과제별 관찰과 캐시 하한 증명

## 실행

Python 3, dig, Wireshark의 tshark가 필요하다. Ubuntu/WSL에서는 dig가 dnsutils 패키지에 포함된다. Windows에서는 PATH의 dig를 우선 사용하며, 없으면 WSL의 dig를 호출한다. 보고서는 Windows 기본 설치 위치의 tshark도 찾는다.

```bash
python3 task1_resolve.py --verify
python3 task1_resolve.py www.stanford.edu --stats --trace-json out/task1_stanford_trace.json
python3 task2_steering.py --collect --network "학교 Wi-Fi"
# 실제 네트워크를 휴대폰 테더링으로 전환한 뒤:
python3 task2_steering.py --collect --network "휴대폰 테더링"
python3 task2_steering.py --report --networks "학교 Wi-Fi" "휴대폰 테더링"
python3 bench.py --yours
python3 test_tasks.py
python3 -m unittest test_regressions.py
```

`--collect`에는 실제 네트워크를 식별하는 `--network NAME`을 반드시 지정한다. 이름은 자유롭게 정할 수 있다. `--report --networks NAME1 NAME2`는 선택한 두 이름의 최신 완료 run으로 72개 조합을 검증한다. 이름이 확인된 완료 네트워크가 정확히 두 개면 `--report`만으로 자동 선택한다. 한 개 또는 세 개 이상이면 명확한 선택을 요구하며 보고서를 덮어쓰지 않는다. 과거의 `current-network`, `현재 네트워크 이름` 같은 기본 라벨은 자동 집계에서 제외하고 새 수집에서는 거부한다.

라벨만 바꾸어 같은 네트워크에서 수집하면 B3를 충족하지 않는다. 현재 보고서는 기존 2026-09-16 두 네트워크 기록과 기존 캡처를 재분석한 것이며 새로 네트워크를 전환했다고 주장하지 않는다. 2026-09-30 `current-network` 기록은 추가 자료로만 보존했다. 실제 두 네트워크 사용 여부는 측정자가 확인해야 한다.

Task 1의 `--stats`는 전체 질의와 glue 누락 보조 질의를 분리한다. `out/task1_stanford_trace.json`은 2026-10-06 재측정 근거다. NS 이름 해석 안에서 발생한 하위 NS 조회나 CNAME 재시작도 보조 조회에 포함하며 중복 합산하지 않는다. UDP→TCP 재시도는 별도 논리 질의로 세지 않는다.

## 검증 범위

2026-10-06 보완 후 실제 `--verify`는 5/5였고, 오프라인 회귀 테스트 7개가 통과했다. Task 2 재검사는 4 passed/0 failed/1 skipped, Task 3은 2 passed/0 failed/1 skipped였다. 아래의 전체 공식 테스트 수치는 이전 실행 기록이며 이번 재검사와 구분한다.

Task 1은 실제 DNS 비교를 통과했다. Task 3은 upstream 275, stale 0으로 공식 baseline 325/266보다 개선됐다. 테스트 스크립트의 skip은 수동 판정 항목 또는 도구 탐지 한계이며 통과와 구분한다. 패킷은 별도로 Wireshark tshark로 분석해 질의/응답 각 3개, 위임/최종 답변 및 최대 메시지 크기를 확인했다.

공식 테스트 결과는 **11 passed, 0 failed, 4 skipped**였다. 3개 skip은 사람의 확인이 필요한 항목, 1개는 tshark가 PATH에 없는 경우의 자동 skip이다. 설치된 tshark.exe의 절대 경로로 캡처 분석은 별도 수행했다. 이 버전은 DNS response 필드를 `True/False`로 출력하며 공식 테스트는 `1/0`만 세므로 PATH에 추가하면 해당 검사가 잘못 실패할 수 있다. 공식 테스트를 고치거나 데이터를 바꿔 숨기지 않았다. 또한 테스트의 `2 sites` 출력은 JSON의 최상위 키 2개를 센 값이고, 실제 12사이트×3리졸버×2네트워크는 보고서 생성기가 검증한다.

공식 `check.py w03`는 상위 디렉터리 아래 `w03-dns/out/`을 찾는다. 독립 저장소 이름은 `wd03`이지만 파일 구조는 해당 주차 폴더와 동일하다. 공식 형식 검증은 `w03-dns/out` 구조로 복사한 검증용 작업 폴더에서 원본 checker를 실행했다.

## 출처

강의 제공 `bench.py`와 `test_tasks.py`는 다운로드 원본과 SHA-256 일치를 확인했다. `task3_cache.py`는 제공 스켈레톤의 BaselineCache를 유지하고 YourCache를 구현했다. 공식 trace를 자체 캡처로 가장하지 않았으며, 불필요한 개인 트래픽이 포함된 비공개 원본은 업로드하지 않는다.
