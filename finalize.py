#!/usr/bin/env python3
"""Finalize a launch build: put the real domain, phone and street into a token build, then check nothing is left over.

usage:
  python finalize.py <launch-dist> <out-dir> --domain example.com --phone +15551234567 --street "123 Main St"

The launch build contains the tokens __DOMAIN__, __PHONE_E164__, __PHONE_DISPLAY__ and __STREET__ in its HTML, JS,
JSON-LD, sitemap, robots.txt and llms.txt. This script copies the build to <out-dir>, replaces every token, and exits
with an error (and deploys nothing) if any token is left or an input is malformed. Standard library only.
"""
import argparse, os, re, shutil, sys
from urllib.parse import quote_plus

TEXT = ('.html', '.js', '.css', '.json', '.xml', '.txt', '.webmanifest', '.md', '.svg')
TOKEN = re.compile(r'__(DOMAIN|PHONE_E164|PHONE_DISPLAY|STREET)__')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src'); ap.add_argument('out')
    ap.add_argument('--domain', help='bare domain, e.g. brightelectricianaltoona.com (omit if the build already has it)')
    ap.add_argument('--phone', required=True, help='US number in E.164, e.g. +15155550123')
    ap.add_argument('--street', help='street line only, e.g. "123 Main St" (omit if the build already has it)')
    ap.add_argument('--ga4', help='Google Analytics 4 measurement ID, e.g. G-ABC123XYZ (optional)')
    ap.add_argument('--clarity', help='Microsoft Clarity project ID for heatmaps and recordings (optional)')
    ap.add_argument('--gsc-token', help='Google Search Console HTML-tag token, only if DNS verification is not used (optional)')
    a = ap.parse_args()
    domain = (a.domain or '').strip().lower().removeprefix('https://').removeprefix('http://').strip('/')
    if a.domain and not re.fullmatch(r'[a-z0-9-]+(\.[a-z0-9-]+)+', domain):
        sys.exit(f'bad domain: {a.domain}')
    if not re.fullmatch(r'\+1[2-9]\d{2}[2-9]\d{6}', a.phone):
        sys.exit(f'bad phone (need +1 and 10 digits): {a.phone}')
    street = ' '.join((a.street or '').split())
    if a.street is not None and (not street or '__' in street):
        sys.exit('street is empty or malformed')
    if a.ga4 and not re.fullmatch(r'G-[A-Z0-9]{6,12}', a.ga4):
        sys.exit(f'bad GA4 measurement ID: {a.ga4}')
    if a.clarity and not re.fullmatch(r'[a-z0-9]{8,12}', a.clarity):
        sys.exit(f'bad Clarity project ID: {a.clarity}')
    if a.gsc_token and not re.fullmatch(r'[A-Za-z0-9_-]{20,80}', a.gsc_token):
        sys.exit('bad Search Console token')
    head = ''
    if a.gsc_token:
        head += f'<meta name="google-site-verification" content="{a.gsc_token}" />'
    if a.ga4:  # skipped when the browser sends Global Privacy Control; click-to-call is sent as an event
        head += ("<script>(function(){if(navigator.globalPrivacyControl)return;var g='" + a.ga4 + "',s=document.createElement('script');"
                 "s.async=1;s.src='https://www.googletagmanager.com/gtag/js?id='+g;document.head.appendChild(s);window.dataLayer=window.dataLayer||[];"
                 "window.gtag=function(){dataLayer.push(arguments)};gtag('js',new Date());gtag('config',g);"
                 "document.addEventListener('click',function(e){var t=e.target.closest&&e.target.closest('a[href^=\"tel:\"]');"
                 "if(t)gtag('event','click_to_call',{link_url:location.pathname});});})();</script>")
    if a.clarity:  # Clarity masks form inputs by default; also skipped under Global Privacy Control
        head += ("<script>(function(c,l,a,r,i,t,y){if(navigator.globalPrivacyControl)return;c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};"
                 "t=l.createElement(r);t.async=1;t.src='https://www.clarity.ms/tag/'+i;y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);})"
                 "(window,document,'clarity','script','" + a.clarity + "');</script>")
    d = a.phone[2:]
    display = f'({d[:3]}) {d[3:6]}-{d[6:]}'
    if os.path.exists(a.out):
        sys.exit(f'out dir already exists: {a.out}')
    shutil.copytree(a.src, a.out)
    changed = 0
    for root, _, files in os.walk(a.out):
        for f in files:
            if not f.endswith(TEXT):
                continue
            p = os.path.join(root, f)
            t = open(p, encoding='utf-8').read()
            if '__' not in t and not (head and f.endswith('.html')):
                continue
            o = t
            # street inside links (maps URLs) is URL-encoded; everywhere else it is plain text
            if street:
                t = re.sub(r'(href="[^"]*?)__STREET__', lambda m: m.group(1) + quote_plus(street), t)
                t = t.replace('__STREET__', street)
            if domain:
                t = t.replace('__DOMAIN__', domain)
            t = t.replace('__PHONE_E164__', a.phone).replace('__PHONE_DISPLAY__', display)
            if head and f.endswith('.html') and '</head>' in t and 'googletagmanager' not in t and 'clarity.ms' not in t:
                t = t.replace('</head>', head + '</head>', 1)
            if t != o:
                open(p, 'w', encoding='utf-8').write(t); changed += 1
    left = []
    for root, _, files in os.walk(a.out):
        for f in files:
            if f.endswith(TEXT):
                p = os.path.join(root, f)
                if TOKEN.search(open(p, encoding='utf-8').read()):
                    left.append(os.path.relpath(p, a.out))
    if left:
        sys.exit('tokens left in: ' + ', '.join(left[:10]))
    print(f'finalized {changed} files -> {a.out}  domain={domain} phone={display} street={street} ga4={a.ga4 or "-"} clarity={a.clarity or "-"}')

if __name__ == '__main__':
    main()
