# pyre-ignore-all-errors
# Debug script: inspect actual rendered Groww DOM to find correct selectors
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from playwright.sync_api import sync_playwright  # type: ignore

URL = "https://groww.in/mutual-funds/parag-parikh-long-term-value-fund-direct-growth"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    page.goto(URL, timeout=45000, wait_until="networkidle")
    page.wait_for_timeout(3000)

    debug = page.evaluate("""
        () => {
            const body = document.body.innerText;

            // 1. Show context around each keyword
            const keywords = ['Minimum SIP', 'Minimum Lumpsum', 'Exit load', 'Riskometer', 'Risk'];
            const contexts = {};
            for (const kw of keywords) {
                const idx = body.toLowerCase().indexOf(kw.toLowerCase());
                contexts[kw] = idx !== -1
                    ? body.slice(Math.max(0, idx - 30), idx + 250)
                    : 'NOT FOUND';
            }

            // 2. Dump adjacent leaf-element pairs (label => value)
            const allEls = Array.from(document.querySelectorAll('*'));
            const kvPairs = [];
            for (const el of allEls) {
                if (el.children.length === 0) {
                    const txt = (el.innerText || '').trim();
                    if (txt.length > 2 && txt.length < 80) {
                        const next = el.nextElementSibling;
                        if (next) {
                            const val = (next.innerText || '').trim();
                            if (val && val.length < 200) {
                                kvPairs.push(txt + ' => ' + val);
                            }
                        }
                    }
                }
            }

            return { contexts, kvPairs: kvPairs.slice(0, 150) };
        }
    """)

    print("=== KEYWORD CONTEXTS ===")
    for kw, ctx in debug['contexts'].items():
        print(f"\\n--- {kw} ---")
        print(repr(ctx))

    print("\\n\\n=== ADJACENT LABEL => VALUE PAIRS ===")
    for kv in debug['kvPairs']:
        print(kv)

    browser.close()
    print("\\nDone.")
