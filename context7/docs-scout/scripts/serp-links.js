// SPDX-License-Identifier: AGPL-3.0-only
// Organic result links from the search engine page in the current tab, as JSON.
//   ab eval --stdin < serp-links.js
// Engine-agnostic: reads every link inside the results region, unwraps the engines' redirect
// wrappers (DuckDuckGo uddg=, Google /url?q=, Bing u=a1<base64>), drops the engines' own pages,
// ad networks and a few social networks, and de-duplicates by host + path. Docs hosts that share
// an engine's domain (developers.google.com, learn.microsoft.com, ...) are kept. Google's /goto links hide the target;
// they are kept with "redirect": true, and opening one lands on the real page.
(() => {
  // The first results region that really holds links; querySelector on a list would return
  // whichever comes first in the document (Startpage's search form is #search).
  const root = ['#links', '#b_results', 'div#search', 'main', '[role="main"]', '#main']
    .map((sel) => document.querySelector(sel))
    .find((el) => el && el.querySelectorAll('a[href]').length >= 3) || document.body;
  const skipDomain = /(^|\.)(duckduckgo\.com|startpage\.com|bing\.com|ecosia\.org|qwant\.com|gstatic\.com|msn\.com|admarketplace\.net|doubleclick\.net|googleadservices\.com|facebook\.com|instagram\.com|tiktok\.com|twitter\.com|x\.com|linkedin\.com|pinterest\.com)$/;
  const skipExact = /^((www|search)\.)?(google|yahoo)\.[a-z]{2,3}(\.[a-z]{2})?$|^(support|accounts|maps|policies|translate|webcache)\.google\.[a-z.]+$|^(go|privacy|account)\.microsoft\.com$|^search\.brave\.com$/;
  const skipHost = { test: (host) => skipDomain.test(host) || skipExact.test(host) };
  const unwrap = (raw) => {
    let u;
    try { u = new URL(raw, location.href); } catch (e) { return null; }
    const q = u.searchParams;
    if (q.get('uddg')) return { url: q.get('uddg') };
    const target = q.get('q') || q.get('url') || '';
    if (u.pathname === '/url' && /^https?:/.test(target)) return { url: target };
    const b = q.get('u');
    if (/bing\./.test(u.hostname) && b && b.startsWith('a1')) {
      try { return { url: atob(b.slice(2).replace(/-/g, '+').replace(/_/g, '/')) }; } catch (e) { return null; }
    }
    if (/google\./.test(u.hostname) && u.pathname === '/goto') return { url: u.href, redirect: true };
    return { url: u.href };
  };
  const results = [];
  const seen = new Map();
  for (const a of root.querySelectorAll('a[href]')) {
    const hit = unwrap(a.getAttribute('href'));
    if (!hit || !/^https?:\/\//.test(hit.url)) continue;
    let u;
    try { u = new URL(hit.url); } catch (e) { continue; }
    if (!hit.redirect && skipHost.test(u.hostname)) continue;
    if (hit.redirect && !a.querySelector('h3')) continue;
    // A heading in or around the link is the result title; the link text alone is often the site name.
    const heading = a.closest('h2, h3') || a.querySelector('h2, h3');
    const title = (heading || a).innerText.trim().replace(/\s+/g, ' ').slice(0, 120);
    if (title.length < 4) continue;
    const key = hit.redirect ? u.href : u.hostname + u.pathname.replace(/\/$/, '');
    const index = seen.get(key);
    if (index !== undefined) {
      if (heading && !results[index].fromHeading) Object.assign(results[index], { title, fromHeading: true });
      continue;
    }
    if (seen.size >= 10) continue;
    seen.set(key, results.length);
    results.push({ title, url: u.href, ...(hit.redirect ? { redirect: true } : {}), fromHeading: Boolean(heading) });
  }
  for (const r of results) delete r.fromHeading;
  return { engine: location.hostname.replace(/^www\./, ''), title: document.title, count: results.length, results };
})()
