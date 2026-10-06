#!/usr/bin/env python3
"""Week 3 · Task 1 — an iterative DNS resolver using only Python's stdlib."""
import argparse
import ipaddress
import json
import random
import shutil
import socket
import struct
import subprocess
import sys
from datetime import datetime, timezone

ROOT_SERVERS = ["198.41.0.4", "199.9.14.201", "192.33.4.12"]
VERIFY_NAMES = [("www.korea.ac.kr", "stable"), ("dns.google", "stable"),
                ("en.wikipedia.org", "stable"), ("www.stanford.edu", "stable"),
                ("www.microsoft.com", "cdn")]
MAX_DEPTH, QUERY_TIMEOUT = 30, 2.5
TYPE_A, TYPE_NS, TYPE_CNAME = 1, 2, 5


class Resolver:
    """Follow DNS referrals ourselves; every query has recursion disabled."""
    @staticmethod
    def _normalise(name):
        return str(name).rstrip(".").lower()

    @staticmethod
    def _encode_name(name):
        labels = [x.encode("idna") for x in name.rstrip(".").split(".")]
        if any(not x or len(x) > 63 for x in labels):
            raise ValueError("invalid DNS label")
        wire = b"".join(bytes([len(x)]) + x for x in labels) + b"\0"
        if len(wire) > 255:
            raise ValueError("DNS name too long")
        return wire

    def _make_query(self, name):
        query_id = random.randrange(65536)
        # flags=0: the RD bit is clear, so this is not a recursive query.
        return query_id, (struct.pack("!HHHHHH", query_id, 0, 1, 0, 0, 0)
                          + self._encode_name(name) + struct.pack("!HH", TYPE_A, 1))

    @staticmethod
    def _read_name(packet, offset):
        labels, end, jumped, seen = [], offset, False, set()
        while True:
            if offset >= len(packet):
                raise ValueError("truncated DNS name")
            length = packet[offset]
            if length & 0xC0 == 0xC0:  # RFC 1035 compression pointer
                if offset + 1 >= len(packet):
                    raise ValueError("truncated DNS pointer")
                pointer = ((length & 0x3F) << 8) | packet[offset + 1]
                if pointer in seen:
                    raise ValueError("DNS compression-pointer loop")
                seen.add(pointer)
                if not jumped:
                    end, jumped = offset + 2, True
                offset = pointer
            elif length == 0:
                return ".".join(labels), (end if jumped else offset + 1)
            else:
                offset += 1
                if offset + length > len(packet):
                    raise ValueError("truncated DNS label")
                labels.append(packet[offset:offset + length].decode("idna"))
                offset += length
                if not jumped:
                    end = offset

    def _parse_response(self, packet, expected_id):
        if len(packet) < 12:
            raise ValueError("truncated DNS header")
        msg_id, flags, qd, an, ns, ar = struct.unpack("!HHHHHH", packet[:12])
        if msg_id != expected_id:
            raise ValueError("response ID does not match query")
        if not flags & 0x8000:
            raise ValueError("not a DNS response")
        if flags & 0x0200:
            return {"truncated": True}
        offset = 12
        for _ in range(qd):
            _, offset = self._read_name(packet, offset)
            offset += 4

        def records(count):
            nonlocal offset
            result = []
            for _ in range(count):
                owner, offset = self._read_name(packet, offset)
                rtype, rclass, _ttl, rdlength = struct.unpack("!HHIH", packet[offset:offset + 10])
                offset += 10
                start, offset = offset, offset + rdlength
                if offset > len(packet):
                    raise ValueError("truncated DNS record")
                if rtype == TYPE_A and rclass == 1 and rdlength == 4:
                    data = str(ipaddress.ip_address(packet[start:offset]))
                elif rtype in (TYPE_NS, TYPE_CNAME):
                    data, _ = self._read_name(packet, start)
                else:
                    data = None
                result.append((self._normalise(owner), rtype, self._normalise(data) if data else None))
            return result

        return {"rcode": flags & 0xF, "truncated": False, "authoritative": bool(flags & 0x0400),
                "answer": records(an), "authority": records(ns), "additional": records(ar)}

    @staticmethod
    def _receive_exact(sock, count):
        chunks = []
        while count:
            chunk = sock.recv(count)
            if not chunk:
                raise OSError("DNS TCP connection closed early")
            chunks.append(chunk)
            count -= len(chunk)
        return b"".join(chunks)

    def _query(self, server, name):
        query_id, wire = self._make_query(name)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(QUERY_TIMEOUT)
            sock.connect((server, 53))
            sock.send(wire)
            packet = sock.recv(65535)
        response = self._parse_response(packet, query_id)
        if not response["truncated"]:
            return response
        with socket.create_connection((server, 53), timeout=QUERY_TIMEOUT) as sock:
            sock.sendall(struct.pack("!H", len(wire)) + wire)
            length = struct.unpack("!H", self._receive_exact(sock, 2))[0]
            return self._parse_response(self._receive_exact(sock, length), query_id)

    def resolve(self, name, depth=0):
        self.query_log = []
        self.ns_walks = 0
        self.cname_restarts = 0
        path, budget = [], [256]
        address = self._walk(name, depth, path, budget, frozenset())
        return address, path

    def _walk(self, name, depth, path, budget, active, auxiliary=False):
        if depth >= MAX_DEPTH:
            raise RuntimeError("maximum delegation/CNAME depth exceeded")
        name, servers = self._normalise(name), list(ROOT_SERVERS)
        if name in active:
            raise RuntimeError("CNAME/NS dependency loop: " + name)
        active = active | {name}
        visited = set()
        while servers:
            next_servers = []
            for server in servers:
                if server in visited:
                    continue
                visited.add(server)
                if budget[0] <= 0:
                    raise RuntimeError("maximum total DNS query count exceeded")
                budget[0] -= 1
                path.append(server)
                # One entry per logical query; a UDP-to-TCP retry is not a new hop.
                event = {"server": server, "name": name,
                         "purpose": "no_glue_ns" if auxiliary else "requested_name",
                         "depth": depth}
                self.query_log.append(event)
                try:
                    response = self._query(server, name)
                except (OSError, ValueError, struct.error) as exc:
                    event["error"] = str(exc)
                    continue  # A failed server is skipped in favour of a peer.
                event["rcode"] = response["rcode"]
                if response["rcode"] != 0:
                    continue
                cname = None
                for owner, rtype, data in response["answer"]:
                    if owner != name or not response["authoritative"]:
                        continue
                    if rtype == TYPE_A and data:
                        return data
                    if rtype == TYPE_CNAME:
                        cname = data
                if cname:
                    self.cname_restarts += 1
                    return self._walk(cname, depth + 1, path, budget, active, auxiliary)
                ns_names = [data for _owner, rtype, data in response["authority"]
                            if rtype == TYPE_NS and data]
                if not ns_names:
                    continue
                glue = {}
                for owner, rtype, data in response["additional"]:
                    if rtype == TYPE_A:
                        glue.setdefault(owner, []).append(data)
                for ns_name in ns_names:
                    if ns_name in glue:
                        next_servers.extend(glue[ns_name])
                    else:  # No glue: make a separate iterative walk for this NS hostname.
                        self.ns_walks += 1
                        try:
                            ns_ip = self._walk(ns_name, depth + 1, path, budget, active, True)
                            next_servers.append(ns_ip)
                        except RuntimeError:
                            pass
                if next_servers:
                    break
            servers = list(dict.fromkeys(next_servers))
        raise RuntimeError(f"could not obtain an A record for {name}")


def dig_answer(name):
    """Compare against dig; on Windows, use dig installed inside WSL."""
    if shutil.which("dig"):
        command = ["dig", "+short", name, "A"]
    elif shutil.which("wsl.exe") or shutil.which("wsl"):
        # Running the Python file from PowerShell can still use WSL's dig.
        command = ["wsl.exe", "--exec", "dig", "+short", name, "A"]
    else:
        raise RuntimeError("dig is not installed (install dnsutils in WSL)")
    result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=30)
    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown error"
        raise RuntimeError(f"dig could not run: {detail}")
    out = result.stdout
    addresses = []
    for line in out.split():
        try:
            addresses.append(str(ipaddress.IPv4Address(line)))
        except ipaddress.AddressValueError:
            pass
    if not addresses:
        raise RuntimeError("dig returned no IPv4 addresses; comparison unavailable")
    return addresses


def verify():
    resolver, failures = Resolver(), 0
    for name, kind in VERIFY_NAMES:
        try:
            addr, path = resolver.resolve(name)
            expected = dig_answer(name)
        except Exception as exc:
            print(f"  FAIL  {name:<22} your resolver raised {exc!r}")
            failures += 1
            continue
        if addr in expected:
            note = ""
        elif kind == "cdn":
            note = "  <- differs, but this name is CDN-hosted. Explain it."
        else:
            note = "  <- should have matched"
            failures += 1
        print(f"  {'FAIL' if note.endswith('matched') else 'ok  '}  {name:<22} "
              f"you={addr:<16} dig={','.join(expected) or '-'} hops={len(path)}{note}")
    print(f"\n  {len(VERIFY_NAMES) - failures}/{len(VERIFY_NAMES)} ok")
    return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("name", nargs="?", default="www.korea.ac.kr")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--stats", action="store_true", help="Show no-glue query counts")
    parser.add_argument("--trace-json", help="Save this single-name query trace as JSON")
    args = parser.parse_args()
    if args.verify:
        if args.stats or args.trace_json:
            parser.error("--stats/--trace-json are for a single-name run, not --verify")
        sys.exit(verify())
    resolver = Resolver()
    address, path = resolver.resolve(args.name)
    for index, server in enumerate(path, 1):
        print(f"  {index}. asked {server}")
    print(f"\n  {args.name} -> {address}")
    auxiliary = sum(q["purpose"] == "no_glue_ns" for q in resolver.query_log)
    stats = {"total_queries": len(path), "no_glue_queries": auxiliary,
             "requested_name_queries": len(path) - auxiliary,
             "ns_walks": resolver.ns_walks, "cname_restarts": resolver.cname_restarts}
    if args.stats:
        print(json.dumps(stats, indent=2))
    if args.trace_json:
        with open(args.trace_json, "w", encoding="utf-8") as stream:
            json.dump({"measured_at": datetime.now(timezone.utc).isoformat(),
                       "name": args.name, "address": address, "stats": stats,
                       "queries": resolver.query_log}, stream, indent=2)
            stream.write("\n")


if __name__ == "__main__":
    main()
