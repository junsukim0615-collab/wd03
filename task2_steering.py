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
    """Analyze the latest completed run, without replacing failed DNS data."""
    with open(os.path.join(OUT, "chains.json"), encoding="utf-8") as stream:
        data = json.load(stream)
    runs = [r for r in data["runs"] if r.get("completed")]
    if not runs:
        raise ValueError("No completed run. Run --collect first.")
    run = max(runs, key=lambda r: r["started_at"])
    lines = ["# Task 2: DNS steering report", "",
             f"Run: {run['run_id']}; network label: {run['network']}",
             f"UTC: {run['started_at']} to {run['finished_at']}", "",
             "Chain length counts CNAME edges. Final zone below is an operational "
             "domain label, not a zone cut verified with SOA queries.", "",
             "Rule R (baseline): different last two labels imply third-party CDN. "
             "The evidence-based classification checks known provider suffixes and "
             "same-organization exceptions separately.", "",
             "| Site | Chain length | Final zone | Third party? | Rule R verdict |",
             "|---|---|---|---|---|"]
    classifications, comparisons, counterexamples = {}, {}, []
    details = []
    for site in SITES:
        results = run["sites"].get(site, {})
        good = [v for v in results.values() if v.get("success")
                and v.get("chain_complete") and v.get("addresses")]
        chains = sorted({tuple(v["chain"]) for v in good})
        kind, reason = classify(site, chains)
        classifications[site] = kind
        verdicts = {last_two(site) != last_two(c[-1]) for c in chains}
        baseline = ", ".join("yes" if v else "no" for v in sorted(verdicts)) or "unknown"
        zones = ", ".join(sorted({final_zone(c[-1]) for c in chains})) or "unknown"
        lengths = ", ".join(map(str, sorted({len(c)-1 for c in chains}))) or "unknown"
        lines.append(f"| {site} | {lengths} | {zones} | {reason} | {baseline} |")
        if kind == "own" and True in verdicts:
            counterexamples.append(f"- {site}: `{' -> '.join(chains[0])}`. Rule R says "
                                   "third party, but this is Wikimedia's own CDN. "
                                   "Different domain names do not imply different organizations.")
        # A failed/empty lookup is not an address-set difference.
        comparisons[site] = (len(good) >= 2,
                             len({frozenset(v['addresses']) for v in good}) > 1)
        for label, result in results.items():
            details += [f"### {site} / {label}", "",
                        "Chain: `" + " -> ".join(result["chain"]) + "`",
                        "A: `" + ", ".join(result["addresses"]) + "`",
                        "Errors: " + ("; ".join(result["errors"]) or "none"), ""]
    lines += ["", "## Actual classification error", ""] + (counterexamples or [
        "No observed counterexample in this run. The required empirical error example "
        "is not satisfied by these measurements; do not invent one."])
    lines += ["", "The last-two-label rule also collapses bbc.co.uk to co.uk and "
              "korea.ac.kr to ac.kr. CloudFront and S3 must not be conflated: "
              "cloudfront.net identifies a CDN; amazonaws.com alone does not.", "",
              "## Resolver comparison", "",
              "Compare successful, nonempty IPv4 sets within this run; ignore ordering. "
              "A site needs at least two successful resolver measurements.", "",
              "| Site | CDN category | Comparable? | Different sets? |",
              "|---|---|---|---|"]
    for site in SITES:
        comparable, different = comparisons[site]
        lines.append(f"| {site} | {classifications[site]} | {comparable} | "
                     f"{different if comparable else 'unknown'} |")
    for title, kinds in [("Service-level CDN", {"external", "own", "service"}),
                         ("Hostname-supported CDN (excludes Netflix)", {"external", "own"}),
                         ("Third-party CDN only", {"external"})]:
        classified = [s for s in SITES if classifications[s] in kinds]
        eligible = [s for s in classified if comparisons[s][0]]
        changed = sum(comparisons[s][1] for s in eligible)
        lines += ["", f"**{title}: {changed} of {len(eligible)} sites answered differently "
                  "to a different resolver.** "
                  f"{len(classified)-len(eligible)} classified sites excluded due to missing data."]
    lines += ["", "## Interpretation and limitations", "",
              "Resolver-dependent answers are compatible with DNS steering, but do not "
              "prove that a replica is geographically closer. Queries are sequential; "
              "time, caching, load balancing and answer subsets may also change results. "
              "Google and Quad9 use anycast; their different addresses do not prove that "
              "the answering resolver instances are in different places. No RTT or server "
              "geolocation was measured. Equal IPs do not rule out anycast steering.", "",
              "Netflix is included only in the service-level count, following the assignment's "
              "own-CDN example. Resolving www.netflix.com does not measure Open Connect video "
              "delivery. Unknown sites are excluded, not declared non-CDN. CNAME absence "
              "does not prove CDN absence.", "", "## Classification references", "",
              "- [Wikimedia CDN](https://wikitech.wikimedia.org/wiki/CDN)",
              "- [Netflix Open Connect](https://openconnect.netflix.com/en/)",
              "- [Akamai edge hostnames](https://techdocs.akamai.com/edge-hostnames/docs/edge-hn-terminology)",
              "- [Fastly routing](https://www.fastly.com/documentation/guides/concepts/routing-traffic-to-fastly/)",
              "- [Netlify DNS](https://docs.netlify.com/manage/domains/configure-domains/configure-external-dns/)",
              "", "## Measured chains and addresses", ""] + details
    path = os.path.join(OUT, "report.md")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print("Saved " + path)


def last_two(name):
    return ".".join(normalize(name).split(".")[-2:])


def suffix(name, domain):
    return name == domain or name.endswith("." + domain)


def final_zone(name):
    for domain in ("korea.ac.kr", "bbc.co.uk"):
        if suffix(name, domain):
            return domain
    return last_two(name)


def classify(site, chains):
    providers = {"edgekey.net": "Akamai", "edgesuite.net": "Akamai",
                 "akamaiedge.net": "Akamai", "akamai.net": "Akamai",
                 "fastly.net": "Fastly", "netlifyglobalcdn.com": "Netlify",
                 "cloudfront.net": "CloudFront"}
    found = {provider for chain in chains for name in chain
             for domain, provider in providers.items() if suffix(name, domain)}
    if found:
        return "external", "yes: " + ", ".join(sorted(found))
    if site == "www.wikipedia.org" and chains and all(
            suffix(c[-1], "wikimedia.org") for c in chains):
        return "own", "no: Wikimedia own CDN"
    if site == "www.netflix.com" and chains:
        return "service", "not established for this host; Netflix owns Open Connect"
    return "unknown", "unknown (not evidence of absence)"


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
