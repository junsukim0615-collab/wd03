#!/usr/bin/env python3
"""Week 3 · Task 2 — Does DNS actually steer you? Measure it.

Textbook §2.4.3 (records) and §2.5 (CDNs).

The lecture claims two things:

    (a) most large sites are served by a CDN, reached through a CNAME chain
    (b) DNS steers each user to a *nearby* replica

Both are testable from your laptop, and one of them is harder to prove than
the slide makes it look. Your job is to produce the evidence and a number.

    python3 task2_steering.py --collect        # gather the raw data
    python3 task2_steering.py --report         # your analysis

What you have to build
----------------------
1.  For each hostname in SITES, follow the CNAME chain to its end and record
    every hop. `--collect` should leave the raw data in out/chains.json.

2.  Decide, for each site, whether it is served by a **third party**.
    This is the hard part and there is no single right answer:

      - `www.microsoft.com` ends at `akamaiedge.net`     - clearly third party
      - `www.netflix.com`   stops inside `netflix.com`   - own CDN, not third party
      - some sites have no CNAME at all and still sit behind a CDN (anycast)
      - `foo.cloudfront.net` and `foo.s3.amazonaws.com` are both Amazon,
        but they are not the same service

    Write down the rule you used and **defend it in observation.md**. A rule
    that just compares the last two labels will be wrong on at least one of
    the sites below; find which, and say so.

3.  Ask **two different resolvers** for the same name and compare the
    addresses you get back. If DNS really steers by location, a CDN-hosted
    name should answer differently to resolvers sitting in different places.

        RESOLVERS below has your system resolver and two public ones.

    Report: of N CDN-hosted sites, how many returned a different address set
    from a different resolver? Claim (b) predicts most of them. Check it.

Pass condition
--------------
There is no fixed answer. You pass by producing, in out/report.md:

  - the table: site | chain length | final zone | third party? | your rule's verdict
  - the steering number: "X of N sites answered differently to a different resolver"
  - at least one site where your classification rule was wrong, and why
"""
import argparse, json, os, subprocess
import ipaddress
import re
import shutil
import tempfile
import uuid
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")

SITES = [
    "www.microsoft.com",     # Akamai, multi-hop
    "www.netflix.com",       # own CDN
    "www.adobe.com",
    "www.cnn.com",
    "www.apple.com",
    "www.korea.ac.kr",       # no CDN at all
    "www.stanford.edu",
    "www.bbc.co.uk",
    "www.spotify.com",
    "www.github.com",
    "www.wikipedia.org",
    "www.nytimes.com",
]

RESOLVERS = {
    "system": None,          # whatever is in your resolv.conf
    "google": "8.8.8.8",
    "quad9":  "9.9.9.9",
}


def lookup(name, rtype="A", server=None):
    """Keep DNS status and the actual responding resolver, including failures."""
    args = ["dig", "+time=3", "+tries=1", "+noall", "+comments",
            "+answer", "+stats", name, rtype]
    if server:
        args.insert(1, f"@{server}")
    if shutil.which("dig") is None and shutil.which("wsl.exe"):
        args = ["wsl.exe", "--exec"] + args
    result = {"name": name, "type": rtype, "queried_at": now(),
              "status": None, "server": None, "records": [], "error": None}
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=12)
    except (OSError, subprocess.TimeoutExpired) as exc:
        result["error"] = str(exc)
        return result
    result["raw_output"] = proc.stdout
    result["stderr"] = proc.stderr
    status = re.search(r"status:\s*([A-Z0-9]+)", proc.stdout)
    responder = re.search(r"^;; SERVER:\s*(.+)$", proc.stdout, re.MULTILINE)
    result["status"] = status.group(1) if status else None
    result["server"] = responder.group(1).strip() if responder else None
    for line in proc.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 5 and not line.startswith(";") and fields[2] == "IN":
            result["records"].append({"name": normalize(fields[0]),
                                      "type": fields[3], "value": fields[4]})
    if proc.returncode != 0 or result["status"] != "NOERROR":
        result["error"] = f"dig exit={proc.returncode}, DNS status={result['status']}"
    return result


def dig(name, rtype="A", server=None):
    """Compatibility helper; unlike +short, failed queries raise an error."""
    result = lookup(name, rtype, server)
    if result["error"]:
        raise RuntimeError(result["error"])
    return [record["value"] for record in result["records"]]


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize(name):
    return name.rstrip(".").lower()


def measure(site, server):
    """Follow this resolver's CNAME chain and query the original name for A."""
    chain = [normalize(site)]
    queries, errors = [], []
    complete = False
    for _ in range(32):
        query = lookup(chain[-1], "CNAME", server)
        queries.append(query)
        if query["error"]:
            errors.append("CNAME: " + query["error"])
            break
        targets = {normalize(r["value"]) for r in query["records"]
                   if r["type"] == "CNAME" and r["name"] == chain[-1]}
        if not targets:
            complete = True
            break
        if len(targets) != 1:
            errors.append("Multiple CNAME targets for one name")
            break
        target = targets.pop()
        if target in chain:
            errors.append("CNAME loop: " + target)
            break
        chain.append(target)
    else:
        errors.append("CNAME traversal limit (32 queries) reached")

    answer = lookup(site, "A", server)
    queries.append(answer)
    addresses = set()
    if answer["error"]:
        errors.append("A: " + answer["error"])
    else:
        for record in answer["records"]:
            if record["type"] == "A":
                try:
                    addresses.add(str(ipaddress.IPv4Address(record["value"])))
                except ipaddress.AddressValueError:
                    errors.append("Invalid IPv4 address: " + record["value"])
    return {"chain": chain, "chain_length": len(chain) - 1,
            "chain_complete": complete,
            "final_name": chain[-1] if complete else None,
            "addresses": sorted(addresses, key=ipaddress.IPv4Address),
            "a_status": answer["status"],
            "success": not errors, "errors": errors, "queries": queries}


def save_data(path, data):
    """Atomic replacement keeps the previous JSON intact if writing fails."""
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def collect(network):
    """Append a named network run; checkpoint after each site/resolver pair."""
    network = network.strip()
    if not network:
        raise ValueError("A nonempty network name is required")
    if shutil.which("dig") is None and shutil.which("wsl.exe") is None:
        raise RuntimeError("dig was not found. Install dig and add it to PATH first.")
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, "chains.json")
    data = {"schema_version": 1, "runs": []}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as stream:
            data = json.load(stream)
        if (not isinstance(data, dict) or data.get("schema_version") != 1
                or not isinstance(data.get("runs"), list)):
            raise ValueError("Existing chains.json has an unsupported format; file preserved")
    run = {"run_id": str(uuid.uuid4()), "network": network,
           "started_at": now(), "finished_at": None, "completed": False,
           "resolvers": dict(RESOLVERS), "sites": {}}
    data["runs"].append(run)
    save_data(path, data)
    for site in SITES:
        run["sites"][site] = {}
        for label, server in RESOLVERS.items():
            result = measure(site, server)
            run["sites"][site][label] = result
            save_data(path, data)
            state = ", ".join(result["addresses"]) or "no A records"
            if result["errors"]:
                state = "; ".join(result["errors"])
            print(f"[{network}] {site} / {label}: {state}", flush=True)
    run["finished_at"] = now()
    run["completed"] = True
    save_data(path, data)
    print(f"Saved run {run['run_id']} to {path}")


def report():
    """Analyze saved runs only; read packet evidence with Wireshark's tshark."""
    with open(os.path.join(OUT, "chains.json"), encoding="utf-8") as stream:
        data = json.load(stream)
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported chains.json schema")
    networks = ["학교 Wi-Fi", "휴대폰 테더링"]
    runs = []
    for network in networks:
        candidates = [r for r in data["runs"]
                      if r.get("network") == network and r.get("completed")]
        if not candidates:
            raise ValueError(f"No completed run for {network}")
        run = max(candidates, key=lambda r: r["started_at"])
        for site in SITES:
            for resolver in RESOLVERS:
                result = run.get("sites", {}).get(site, {}).get(resolver, {})
                if (not result.get("success") or not result.get("chain_complete")
                        or not result.get("addresses") or result.get("errors")):
                    raise ValueError(f"Incomplete evidence: {network}/{site}/{resolver}")
                chain = result.get("chain", [])
                if (not chain or chain[0] != site or len(set(chain)) != len(chain)
                        or result.get("chain_length") != len(chain) - 1
                        or result.get("final_name") != chain[-1]):
                    raise ValueError(f"Invalid chain: {network}/{site}/{resolver}")
                for address in result["addresses"]:
                    ipaddress.IPv4Address(address)
        runs.append(run)

    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ")

    def last_two(name):
        return ".".join(normalize(name).split(".")[-2:])

    providers = {"edgekey.net": "Akamai", "edgesuite.net": "Akamai",
                 "akamaiedge.net": "Akamai", "akamai.net": "Akamai",
                 "fastly.net": "Fastly", "netlifyglobalcdn.com": "Netlify"}
    lines = ["# Task 2 — DNS capture and steering report", "", "## 측정 환경", "",
             "학교 Wi-Fi와 휴대폰 테더링의 최신 완료 기록을 선택했다. "
             "`현재 네트워크 이름` 기록과 미완료 기록은 제외했다.", ""]
    for run in runs:
        lines.append(f"- {cell(run['network'])}: {run['started_at']} ~ "
                     f"{run['finished_at']} (UTC), run ID `{run['run_id']}`")
    lines += ["", "리졸버: system, Google 8.8.8.8, Quad9 9.9.9.9. "
              "각 네트워크 12개 사이트 × 3개 리졸버의 결과를 검증했다.", "",
              "## B4. Third-party CDN classification / 제3자 CDN 분류", "",
              "규칙 R: 원래 이름과 최종 이름의 마지막 두 라벨이 다르면 제3자로 판정한다. "
              "별도로 알려진 CDN 도메인과 운영 주체를 근거로 분류한다. "
              "CNAME 부재나 같은 도메인이라는 사실은 CDN 부재를 증명하지 않는다.", "",
              "최종 zone은 SOA로 검증한 zone cut이 아닌 운영 도메인 표기다. "
              "서로 다른 체인은 모두 표시한다. 제3자 미확인은 부재 확정이 아니다.", "",
              "| 사이트 | 체인 길이 | 최종 zone | 제3자 여부 / 근거 | 규칙 R 판정 |",
              "|---|---|---|---|---|"]
    classifications, changes, chain_rows, address_rows = {}, {}, [], []
    for site in SITES:
        results = [r["sites"][site][k] for r in runs for k in RESOLVERS]
        chains = sorted({tuple(v["chain"]) for v in results})
        found = {provider for chain in chains for host in chain
                 for suffix, provider in providers.items()
                 if host == suffix or host.endswith("." + suffix)}
        if found:
            kind, reason = "external", "예 — " + ", ".join(sorted(found))
        elif site == "www.wikipedia.org" and all(
                last_two(c[-1]) == "wikimedia.org" for c in chains):
            kind, reason = "own", "아니오 — Wikimedia 자체 CDN"
        elif site == "www.netflix.com" and all(
                last_two(c[-1]) == "netflix.com" for c in chains):
            kind, reason = "service", "외부 미확인 — 서비스 단위 자체 CDN"
        else:
            kind, reason = "unknown", "외부 CDN 미확인; CDN 집계 제외"
        classifications[site] = kind
        verdicts = {"예" if last_two(site) != last_two(c[-1]) else "아니오" for c in chains}
        zones = {"korea.ac.kr" if c[-1].endswith(".korea.ac.kr") else last_two(c[-1]) for c in chains}
        lengths = sorted({len(c) - 1 for c in chains})
        lines.append(f"| {site} | {', '.join(map(str, lengths))} | "
                     f"{', '.join(sorted(zones))} | {reason} | {', '.join(sorted(verdicts))} |")
        sets = [[frozenset(r["sites"][site][k]["addresses"]) for k in RESOLVERS] for r in runs]
        resolver_diff = any(len(set(group)) > 1 for group in sets)
        network_diff = any(x != y for x, y in zip(*sets))
        changes[site] = (resolver_diff, network_diff)
        for chain in chains:
            chain_rows.append(f"- `{site}`: `{' → '.join(chain)}`")
        for run in runs:
            for resolver in RESOLVERS:
                result = run["sites"][site][resolver]
                addresses = sorted(set(result["addresses"]), key=ipaddress.IPv4Address)
                servers = sorted({q.get("server") for q in result.get("queries", []) if q.get("server")})
                address_rows.append(f"| {cell(run['network'])} | {site} | {resolver} | "
                                    f"{', '.join(addresses)} | {cell(', '.join(servers))} |")
    wiki = runs[0]["sites"]["www.wikipedia.org"]["system"]["chain"]
    if classifications["www.wikipedia.org"] != "own" or last_two(wiki[0]) == last_two(wiki[-1]):
        raise ValueError("Saved Wikipedia chain no longer supports the documented counterexample")
    lines += ["", "### 규칙의 실제 오판", "",
              f"Wikipedia의 관측 체인은 `{' → '.join(wiki)}`이다. "
              "규칙 R은 wikipedia.org와 wikimedia.org를 다른 조직으로 오인하여 제3자로 판정한다. "
              "그러나 Wikimedia가 자체 CDN을 운영하므로 거짓 양성이다. "
              "도메인 차이는 운영 조직 차이와 같지 않다. [Wikimedia CDN](https://wikitech.wikimedia.org/wiki/CDN)", "",
              "마지막 두 라벨은 BBC를 co.uk, 고려대를 ac.kr로 축약하는 한계도 있다. "
              "이번 BBC의 외부 Fastly 판정 자체는 맞으므로 이를 실제 오판 사례로 세지 않는다.", "",
              "### 분류 근거와 분모", "",
              "Akamai/Fastly/Netlify 도메인은 외부 CDN 근거로 사용했다. "
              "[Akamai](https://techdocs.akamai.com/edge-hostnames/docs/edge-hn-terminology), "
              "[Fastly](https://www.fastly.com/documentation/guides/concepts/routing-traffic-to-fastly/), "
              "[Netlify](https://answers.netlify.com/t/how-can-i-change-which-netlify-site-my-hostname-is-pointing-to/3259)", "",
              "Netflix는 과제의 서비스 단위 분류에 따라 자체 CDN 서비스로 포함했다. "
              "다만 www.netflix.com의 DNS 조회는 영상 CDN 경로를 직접 측정한 것이 아니다. "
              "[Netflix Open Connect](https://openconnect.netflix.com/en/). "
              "GitHub의 주소 변화만으로 CDN이라고 판단하지 않으며, 고려대와 함께 분모에서 제외한다.", "",
              "## B5. Resolver and network steering 비교", "",
              "IPv4 주소 집합으로 비교하여 순서와 중복은 무시한다. 같은 네트워크에서 리졸버끼리, "
              "같은 리졸버에서 네트워크끼리 비교한다. 하나라도 차이가 있으면 사이트를 한 번 센다.", "",
              "| 사이트 | CDN 집계 | 리졸버 차이 | 네트워크 차이 |",
              "|---|---|---|---|"]
    for site, (rd, nd) in changes.items():
        lines.append(f"| {site} | {'포함' if classifications[site] != 'unknown' else '제외'} | "
                     f"{'있음' if rd else '없음'} | {'있음' if nd else '없음'} |")
    for label, kinds in [("서비스 단위 주 집계", {"external", "own", "service"}),
                         ("Netflix 제외 보조 집계", {"external", "own"}),
                         ("제3자 CDN만 집계", {"external"})]:
        selected = [s for s in SITES if classifications[s] in kinds]
        n = len(selected)
        m = sum(any(changes[s]) for s in selected)
        rd = sum(changes[s][0] for s in selected)
        nd = sum(changes[s][1] for s in selected)
        lines += ["", f"**{label}: 학교 Wi-Fi와 휴대폰 테더링에서 CDN 사이트 {n}개 중 "
                  f"{m}개가 리졸버 또는 네트워크에 따라 달랐다 ({m}/{n}).** "
                  f"리졸버 차이 {rd}/{n}, 네트워크 차이 {nd}/{n}."]
    lines += ["", "### 해석과 한계", "",
              "응답 변화는 확인했지만 ‘더 가까운 복제 서버’라는 주장은 입증하지 못한다. "
              "서버 위치, RTT, HTTP 및 영상 전송을 측정하지 않았다. 두 측정의 시간 차이, 캐시와 "
              "부하 분산도 영향을 줄 수 있다. system은 네트워크 변경 시 DNS 서버 자체도 바뀐다. "
              "공개 DNS의 anycast 주소를 물리적 위치로 간주하지 않으며, 같은 IP라고 같은 서버라는 "
              "뜻도 아니다. CDN 사용과 주소 변화, 사용자 위치에 따른 선택을 구분해야 한다.", "",
              "## Part A. 패킷 증거", ""]
    tshark = shutil.which("tshark")
    if not tshark:
        candidate = os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "Wireshark", "tshark.exe")
        if os.path.isfile(candidate):
            tshark = candidate
    if not tshark:
        raise RuntimeError("Wireshark tshark is required to verify Part A")
    capture = os.path.join(OUT, "dns.pcapng")
    # Fields output provides stable scalar metadata; detailed NS/A sections below
    # are validated independently with display filters.
    fields = ["frame.number", "frame.len", "dns.id", "dns.flags.response", "dns.qry.name",
              "dns.count.answers", "dns.count.auth_rr", "dns.count.add_rr", "udp.length",
              "dns.response_to", "ip.src", "ip.dst", "dns.a"]
    def packets(display_filter):
        args = [tshark, "-r", capture, "-Y", display_filter, "-T", "fields"]
        for field in fields:
            args += ["-e", field]
        proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=30)
        if proc.returncode:
            raise RuntimeError(proc.stderr)
        return [dict(zip(fields, line.split("\t"))) for line in proc.stdout.splitlines()]
    responses = packets("dns.flags.response == 1")
    referrals = packets('dns.flags.response == 1 && dns.qry.name == "www.korea.ac.kr" && dns.count.answers == 0 && dns.ns')
    answers = packets('dns.flags.response == 1 && dns.qry.name == "www.korea.ac.kr" && dns.count.answers > 0 && dns.a')
    if not responses or not referrals or not answers:
        raise ValueError("Capture does not contain the required referral and answer evidence")
    referral, answer = referrals[0], answers[-1]
    query_num = referral["dns.response_to"]
    query = packets(f"frame.number == {int(query_num)}")[0]
    if query["dns.id"] != referral["dns.id"] or query["ip.src"] != referral["ip.dst"]:
        raise ValueError("Query/response match failed")
    lines += ["- 파일: `out/dns.pcapng` (실측 패킷)",
              f"- 질의 {query_num}번 ↔ 응답 {referral['frame.number']}번: Transaction ID `{referral['dns.id']}`.",
              f"- 위임 응답 {referral['frame.number']}번: Answer {referral['dns.count.answers']}개, "
              f"Authority {referral['dns.count.auth_rr']}개, NS 레코드 존재.",
              f"- 최종 답변 {answer['frame.number']}번: Answer {answer['dns.count.answers']}개, A 주소 `{answer['dns.a']}`."]
    if any(not r["udp.length"].isdigit() for r in responses):
        raise ValueError("TCP DNS capture requires an explicit DNS message size calculation")
    largest = max(responses, key=lambda r: int(r["udp.length"]) - 8)
    lines += [f"- 최대 DNS 응답 {largest['frame.number']}번: DNS 메시지 "
              f"**{int(largest['udp.length']) - 8}바이트**, 프레임 전체 **{largest['frame.len']}바이트**. "
              "DNS 길이는 UDP 길이에서 UDP 헤더 8바이트를 뺀 값이다.",
              f"- 이 응답에는 Answer {largest['dns.count.answers']}개, Authority "
              f"{largest['dns.count.auth_rr']}개, Additional {largest['dns.count.add_rr']}개가 들어 있다. "
              "위임 NS와 추가 주소 레코드가 많은 응답은 최종 A 답변보다 클 수 있다.", "",
              "기존 Downloads/out의 캡처 로그는 Wi-Fi 인터페이스에서 수집했다고 기록한다. "
              "제출용 파일은 Task 1 패킷만 남긴 파일이며 원본 비공개 캡처는 제출에서 제외한다. "
              "pcap과 수집 로그만으로 물리적 장소를 증명할 수는 없다.", "",
              "## 부록: 관측 CNAME 체인", ""] + chain_rows
    lines += ["", "## 부록: 네트워크·리졸버별 주소 집합", "",
              "| 네트워크 | 사이트 | 리졸버 | IPv4 주소 집합 | 응답 서버 |",
              "|---|---|---|---|---|"] + address_rows
    destination = os.path.join(OUT, "report.md")
    fd, temporary = tempfile.mkstemp(dir=OUT, suffix=".md.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"Report saved: {destination}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--collect", action="store_true")
    mode.add_argument("--report", action="store_true")
    p.add_argument("--network", default="current-network", help="Actual network label, if known")
    a = p.parse_args()
    os.makedirs(OUT, exist_ok=True)
    if a.collect:
        if not a.network or not a.network.strip():
            p.error("--collect requires --network NAME")
        try:
            collect(a.network)
        except (OSError, ValueError, RuntimeError) as exc:
            p.exit(1, f"Collection failed: {exc}\n")
    elif a.report:
        report()
    else:
        p.print_help()
