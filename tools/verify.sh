#!/usr/bin/env bash
# Usage: tools/verify.sh https://www.kaicovoice.com          (Vercel, clean URLs)
#        tools/verify.sh http://localhost:8123 .html         (local python http.server mirror)
set -u
BASE="${1:?base url}"; EXT="${2:-}"; CK=""; [ -n "${COOKIE:-}" ] && CK="-b $COOKIE"  # COOKIE=/path/jar for protected previews
fail=0
pages="/ /pricing /services/websites /services/phone /industries/hvac /industries/roofing /proof /client-agreement /thanks /sms /privacy /terms"
for p in $pages; do
  url="$BASE$p"; [ "$p" != "/" ] && url="$BASE$p$EXT"
  code=$(curl -s $CK -o /tmp/page.html -w '%{http_code}' "$url"); head=$(curl -s $CK -o /dev/null -I -w '%{http_code}' "$url")
  title=$(grep -o '<title>[^<]*</title>' /tmp/page.html | head -1)
  bad=$(grep -c -E '\$250|cancel anytime|no contract\b|sample data' /tmp/page.html)
  html_links=$(grep -o 'href="/[^"]*\.html"' /tmp/page.html | wc -l | tr -d ' ')
  canon=$(grep -o '<link rel="canonical" href="[^"]*"' /tmp/page.html | head -1)
  printf '%-22s GET %s HEAD %s banned %s .html-links %s %s\n' "$p" "$code" "$head" "$bad" "$html_links" "$title"
  [ "$code" = 200 ] && [ "$head" = 200 ] && [ "$bad" = 0 ] && [ "$html_links" = 0 ] && [ -n "$canon" ] || fail=1
done
printf 'sitemap locs: %s\n' "$(curl -s $CK "$BASE/sitemap.xml" | grep -c '<loc>')"
printf 'llms.txt: %s\n' "$(curl -s $CK -o /dev/null -w '%{http_code}' "$BASE/llms.txt")"
printf 'thanks noindex: %s\n' "$(curl -s $CK "$BASE/thanks$EXT" | grep -c 'noindex')"
printf '404 status: %s\n' "$(curl -s $CK -o /dev/null -w '%{http_code}' "$BASE/definitely-not-a-page")"
exit $fail
