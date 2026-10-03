# Task 2: DNS steering report

Run: cc7c8f90-20b0-4de4-9be9-836d67d638c9; network label: current-network
UTC: 2026-09-30T02:40:55.221870+00:00 to 2026-09-30T02:41:23.977235+00:00

Chain length counts CNAME edges. Final zone below is an operational domain label, not a zone cut verified with SOA queries.

Rule R (baseline): different last two labels imply third-party CDN. The evidence-based classification checks known provider suffixes and same-organization exceptions separately.

| Site | Chain length | Final zone | Third party? | Rule R verdict |
|---|---|---|---|---|
| www.microsoft.com | 2 | akamaiedge.net | yes: Akamai | yes |
| www.netflix.com | 1 | netflix.com | not established for this host; Netflix owns Open Connect | no |
| www.adobe.com | 2 | akamai.net | yes: Akamai | yes |
| www.cnn.com | 1 | fastly.net | yes: Fastly | yes |
| www.apple.com | 3 | akamaiedge.net | yes: Akamai | yes |
| www.korea.ac.kr | 0 | korea.ac.kr | unknown (not evidence of absence) | no |
| www.stanford.edu | 1 | netlifyglobalcdn.com | yes: Netlify | yes |
| www.bbc.co.uk | 2 | fastly.net | yes: Fastly | yes |
| www.spotify.com | 1 | fastly.net | yes: Fastly | yes |
| www.github.com | 1 | github.com | unknown (not evidence of absence) | no |
| www.wikipedia.org | 1 | wikimedia.org | no: Wikimedia own CDN | yes |
| www.nytimes.com | 3 | fastly.net | yes: Fastly | yes |

## Actual classification error

- www.wikipedia.org: `www.wikipedia.org -> dyna.wikimedia.org`. Rule R says third party, but this is Wikimedia's own CDN. Different domain names do not imply different organizations.

The last-two-label rule also collapses bbc.co.uk to co.uk and korea.ac.kr to ac.kr. CloudFront and S3 must not be conflated: cloudfront.net identifies a CDN; amazonaws.com alone does not.

## Resolver comparison

Compare successful, nonempty IPv4 sets within this run; ignore ordering. A site needs at least two successful resolver measurements.

| Site | CDN category | Comparable? | Different sets? |
|---|---|---|---|
| www.microsoft.com | external | True | True |
| www.netflix.com | service | True | False |
| www.adobe.com | external | True | True |
| www.cnn.com | external | True | True |
| www.apple.com | external | True | False |
| www.korea.ac.kr | unknown | True | False |
| www.stanford.edu | external | True | False |
| www.bbc.co.uk | external | True | True |
| www.spotify.com | external | True | True |
| www.github.com | unknown | True | True |
| www.wikipedia.org | own | True | False |
| www.nytimes.com | external | True | True |

**Service-level CDN: 6 of 10 sites answered differently to a different resolver.** 0 classified sites excluded due to missing data.

**Hostname-supported CDN (excludes Netflix): 6 of 9 sites answered differently to a different resolver.** 0 classified sites excluded due to missing data.

**Third-party CDN only: 6 of 8 sites answered differently to a different resolver.** 0 classified sites excluded due to missing data.

## Interpretation and limitations

Resolver-dependent answers are compatible with DNS steering, but do not prove that a replica is geographically closer. Queries are sequential; time, caching, load balancing and answer subsets may also change results. Google and Quad9 use anycast; their different addresses do not prove that the answering resolver instances are in different places. No RTT or server geolocation was measured. Equal IPs do not rule out anycast steering.

Netflix is included only in the service-level count, following the assignment's own-CDN example. Resolving www.netflix.com does not measure Open Connect video delivery. Unknown sites are excluded, not declared non-CDN. CNAME absence does not prove CDN absence.

## Classification references

- [Wikimedia CDN](https://wikitech.wikimedia.org/wiki/CDN)
- [Netflix Open Connect](https://openconnect.netflix.com/en/)
- [Akamai edge hostnames](https://techdocs.akamai.com/edge-hostnames/docs/edge-hn-terminology)
- [Fastly routing](https://www.fastly.com/documentation/guides/concepts/routing-traffic-to-fastly/)
- [Netlify DNS](https://docs.netlify.com/manage/domains/configure-domains/configure-external-dns/)

## Measured chains and addresses

### www.microsoft.com / system

Chain: `www.microsoft.com -> www.microsoft.com-c-3.edgekey.net -> e13678.dscb.akamaiedge.net`
A: `104.76.80.143`
Errors: none

### www.microsoft.com / google

Chain: `www.microsoft.com -> www.microsoft.com-c-3.edgekey.net -> e13678.dscb.akamaiedge.net`
A: `104.76.80.143`
Errors: none

### www.microsoft.com / quad9

Chain: `www.microsoft.com -> www.microsoft.com-c-3.edgekey.net -> e13678.dscb.akamaiedge.net`
A: `23.63.226.92`
Errors: none

### www.netflix.com / system

Chain: `www.netflix.com -> www.prod.ftl.netflix.com`
A: `207.45.72.1, 207.45.73.1`
Errors: none

### www.netflix.com / google

Chain: `www.netflix.com -> www.prod.ftl.netflix.com`
A: `207.45.72.1, 207.45.73.1`
Errors: none

### www.netflix.com / quad9

Chain: `www.netflix.com -> www.prod.ftl.netflix.com`
A: `207.45.72.1, 207.45.73.1`
Errors: none

### www.adobe.com / system

Chain: `www.adobe.com -> www.adobe.com.edgesuite.net -> a1319.dscr.akamai.net`
A: `23.76.153.115, 23.76.153.121`
Errors: none

### www.adobe.com / google

Chain: `www.adobe.com -> www.adobe.com.edgesuite.net -> a1319.dscr.akamai.net`
A: `23.76.153.115, 23.76.153.121`
Errors: none

### www.adobe.com / quad9

Chain: `www.adobe.com -> www.adobe.com.edgesuite.net -> a1319.dscr.akamai.net`
A: `2.22.234.100, 2.22.234.120`
Errors: none

### www.cnn.com / system

Chain: `www.cnn.com -> cnn-tls.map.fastly.net`
A: `146.75.51.5`
Errors: none

### www.cnn.com / google

Chain: `www.cnn.com -> cnn-tls.map.fastly.net`
A: `151.101.3.5, 151.101.67.5, 151.101.131.5, 151.101.195.5`
Errors: none

### www.cnn.com / quad9

Chain: `www.cnn.com -> cnn-tls.map.fastly.net`
A: `151.101.3.5, 151.101.67.5, 151.101.131.5, 151.101.195.5`
Errors: none

### www.apple.com / system

Chain: `www.apple.com -> www-apple-com.v.aaplimg.com -> www.apple.com.edgekey.net -> e6858.dsce9.akamaiedge.net`
A: `184.31.228.249`
Errors: none

### www.apple.com / google

Chain: `www.apple.com -> www-apple-com.v.aaplimg.com -> www.apple.com.edgekey.net -> e6858.dsce9.akamaiedge.net`
A: `184.31.228.249`
Errors: none

### www.apple.com / quad9

Chain: `www.apple.com -> www-apple-com.v.aaplimg.com -> www.apple.com.edgekey.net -> e6858.dsce9.akamaiedge.net`
A: `184.31.228.249`
Errors: none

### www.korea.ac.kr / system

Chain: `www.korea.ac.kr`
A: `163.152.6.10`
Errors: none

### www.korea.ac.kr / google

Chain: `www.korea.ac.kr`
A: `163.152.6.10`
Errors: none

### www.korea.ac.kr / quad9

Chain: `www.korea.ac.kr`
A: `163.152.6.10`
Errors: none

### www.stanford.edu / system

Chain: `www.stanford.edu -> stanford.netlifyglobalcdn.com`
A: `3.33.186.135, 15.197.167.90`
Errors: none

### www.stanford.edu / google

Chain: `www.stanford.edu -> stanford.netlifyglobalcdn.com`
A: `3.33.186.135, 15.197.167.90`
Errors: none

### www.stanford.edu / quad9

Chain: `www.stanford.edu -> stanford.netlifyglobalcdn.com`
A: `3.33.186.135, 15.197.167.90`
Errors: none

### www.bbc.co.uk / system

Chain: `www.bbc.co.uk -> www.bbc.co.uk.pri.bbc.co.uk -> bbc.map.fastly.net`
A: `146.75.48.81`
Errors: none

### www.bbc.co.uk / google

Chain: `www.bbc.co.uk -> www.bbc.co.uk.pri.bbc.co.uk -> bbc.map.fastly.net`
A: `151.101.0.81, 151.101.64.81, 151.101.128.81, 151.101.192.81`
Errors: none

### www.bbc.co.uk / quad9

Chain: `www.bbc.co.uk -> www.bbc.co.uk.pri.bbc.co.uk -> bbc.map.fastly.net`
A: `151.101.0.81, 151.101.64.81, 151.101.128.81, 151.101.192.81`
Errors: none

### www.spotify.com / system

Chain: `www.spotify.com -> atc.spotify.map.fastly.net`
A: `146.75.51.42`
Errors: none

### www.spotify.com / google

Chain: `www.spotify.com -> atc.spotify.map.fastly.net`
A: `151.101.3.42, 151.101.67.42, 151.101.131.42, 151.101.195.42`
Errors: none

### www.spotify.com / quad9

Chain: `www.spotify.com -> atc.spotify.map.fastly.net`
A: `151.101.3.42, 151.101.67.42, 151.101.131.42, 151.101.195.42`
Errors: none

### www.github.com / system

Chain: `www.github.com -> github.com`
A: `20.200.245.247`
Errors: none

### www.github.com / google

Chain: `www.github.com -> github.com`
A: `20.200.245.247`
Errors: none

### www.github.com / quad9

Chain: `www.github.com -> github.com`
A: `20.27.177.113`
Errors: none

### www.wikipedia.org / system

Chain: `www.wikipedia.org -> dyna.wikimedia.org`
A: `103.102.166.224`
Errors: none

### www.wikipedia.org / google

Chain: `www.wikipedia.org -> dyna.wikimedia.org`
A: `103.102.166.224`
Errors: none

### www.wikipedia.org / quad9

Chain: `www.wikipedia.org -> dyna.wikimedia.org`
A: `103.102.166.224`
Errors: none

### www.nytimes.com / system

Chain: `www.nytimes.com -> www.prd.map.nytimes.com -> www.prd.map.nytimes.xovr.nyt.net -> nytimes.map.fastly.net`
A: `146.75.49.164`
Errors: none

### www.nytimes.com / google

Chain: `www.nytimes.com -> www.prd.map.nytimes.com -> www.prd.map.nytimes.xovr.nyt.net -> nytimes.map.fastly.net`
A: `151.101.1.164, 151.101.65.164, 151.101.129.164, 151.101.193.164`
Errors: none

### www.nytimes.com / quad9

Chain: `www.nytimes.com -> www.prd.map.nytimes.com -> www.prd.map.nytimes.xovr.nyt.net -> nytimes.map.fastly.net`
A: `151.101.1.164, 151.101.65.164, 151.101.129.164, 151.101.193.164`
Errors: none

