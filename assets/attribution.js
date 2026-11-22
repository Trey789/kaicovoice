(function () {
  'use strict';
  var key = 'kaico-first-touch', now = Date.now(), expires = now + 1800000, saved;
  function clean(value, max) { return (value || '').replace(/[\x00-\x1f\x7f]/g, '').trim().slice(0, max); }
  function pathOnly(value) {
    if (!value || value.charAt(0) !== '/' || value.slice(0, 2) === '//') return '';
    try { return new URL(value, window.location.origin).pathname.slice(0, 500); } catch (_) { return ''; }
  }
  var params = new URLSearchParams(window.location.search), referrer = '';
  try {
    var host = new URL(document.referrer).hostname;
    if (host !== 'kaicovoice.com' && !host.endsWith('.kaicovoice.com') && host !== window.location.hostname) referrer = clean(host, 200);
  } catch (_) {}
  var canonical = document.querySelector('link[rel="canonical"]');
  var landing = canonical ? pathOnly(new URL(canonical.href).pathname) : '';
  var touch = {
    source: clean(params.get('utm_source'), 200) || referrer || 'unknown',
    medium: clean(params.get('utm_medium'), 100) || (referrer ? 'referral' : 'unknown'),
    campaign: clean(params.get('utm_campaign'), 200), keyword: clean(params.get('utm_term'), 300),
    content: clean(params.get('utm_content'), 200),
    click_id: clean(params.get('gclid') || params.get('msclkid') || params.get('wbraid') || params.get('gbraid'), 300),
    landing_page: landing
  };
  function store() { try { sessionStorage.setItem(key, JSON.stringify({expires: expires, touch: touch})); } catch (_) {} }
  // shortcut: first touch lasts 30 minutes in this tab; use a consented CRM join for cross-device journeys.
  try {
    saved = JSON.parse(sessionStorage.getItem(key));
    if (saved && typeof saved.expires === 'number' && saved.expires > now && saved.expires <= expires && saved.touch &&
        Object.keys(touch).every(function (k) { return typeof saved.touch[k] === 'string' && saved.touch[k].length <= (k === 'landing_page' ? 500 : k === 'keyword' || k === 'click_id' ? 300 : k === 'medium' ? 100 : 200); })) {
      expires = saved.expires;
      Object.keys(touch).forEach(function (k) { touch[k] = clean(saved.touch[k], 500); });
      touch.landing_page = pathOnly(touch.landing_page);
    }
  } catch (_) {}
  store();
  window.kaicoAttribution = function () {
    if (Date.now() >= expires) {
      Object.keys(touch).forEach(function (k) { touch[k] = ''; });
      touch.source = touch.medium = 'unknown'; touch.landing_page = landing;
      expires = Date.now() + 1800000; store();
    }
    return Object.assign({}, touch);
  };
  var originalLinks = new WeakMap();
  function calendarLink(a) {
    var original = originalLinks.get(a) || a.href;
    if (!original.startsWith('https://cal.com/kaicovoice/')) return;
    originalLinks.set(a, original);
    var url = new URL(original), entry = window.kaicoAttribution();
    var creative = clean(url.searchParams.get('utm_content'), 200) || entry.content;
    var tags = {utm_source: entry.source, utm_medium: entry.medium, utm_campaign: entry.campaign,
      utm_term: entry.keyword, utm_content: creative ? JSON.stringify({creative: creative, landing_page: entry.landing_page}) : entry.landing_page};
    Object.keys(tags).forEach(function (k) { if (tags[k] && (k === 'utm_content' || !url.searchParams.has(k))) url.searchParams.set(k, tags[k]); });
    a.href = url.href;
  }
  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('a[href^="https://cal.com/kaicovoice/"]').forEach(calendarLink);
  });
  document.addEventListener('click', function (event) {
    var a = event.target.closest ? event.target.closest('a') : null;
    if (a) calendarLink(a);
  }, true);
})();
