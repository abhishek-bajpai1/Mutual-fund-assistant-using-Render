# pyre-ignore-all-errors
import json
import os
import re
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore
from bs4 import BeautifulSoup  # type: ignore
from playwright.sync_api import sync_playwright, Page  # type: ignore

from schema import SchemeData  # type: ignore

AMC_URL = "https://groww.in/mutual-funds/amc/ppfas-mutual-funds"
SCHEME_URLS = [
    "https://groww.in/mutual-funds/parag-parikh-long-term-value-fund-direct-growth",
    "https://groww.in/mutual-funds/parag-parikh-elss-tax-saver-fund-direct-growth",
    "https://groww.in/mutual-funds/parag-parikh-conservative-hybrid-fund-direct-growth",
    "https://groww.in/mutual-funds/parag-parikh-liquid-fund-direct-growth",
    "https://groww.in/mutual-funds/parag-parikh-arbitrage-fund-direct-growth",
    "https://groww.in/mutual-funds/parag-parikh-dynamic-asset-allocation-fund-direct-growth",
    "https://groww.in/mutual-funds/parag-parikh-large-cap-fund-direct-growth"
]


def extract_metric(soup: BeautifulSoup, keywords: list) -> str:
    """Locate a metric by keyword then return the adjacent sibling value."""
    for keyword in keywords:
        elem = soup.find(string=re.compile(keyword, re.IGNORECASE))
        if elem:
            parent = elem.find_parent()
            if parent:
                next_sib = parent.find_next_sibling()
                if next_sib and next_sib.text.strip():
                    return next_sib.text.strip()
            td = elem.find_parent('td')
            if td:
                next_td = td.find_next_sibling('td')
                if next_td and next_td.text.strip():
                    return next_td.text.strip()
    return "Not specified"


# JavaScript to run in the browser — kept as a module-level constant to avoid
# Python string escape conflicts with JS regex syntax.
_JS_EXTRACT = """
() => {
    const body = document.body.innerText;

    function findSIP() {
        // Label on Groww is "Min. for SIP" with adjacent value e.g. "1,000"
        const allEls = Array.from(document.querySelectorAll('*'));
        for (const el of allEls) {
            const txt = (el.innerText || '').trim();
            if (/^min\\.? ?for sip$/i.test(txt) || /^min\\.? ?sip$/i.test(txt)) {
                const next = el.nextElementSibling;
                if (next) {
                    const val = (next.innerText || '').trim();
                    if (val && val.length < 50) return val;
                }
            }
        }
        // Fallback: extract from body text block
        const m = body.match(/Minimum SIP Investment is (?:set to )?([0-9][0-9,]*)/i);
        return m ? m[1] : null;
    }

    function findLumpsum() {
        // Embedded in a long text paragraph
        const m = body.match(/Minimum Lumpsum Investment is .([0-9][0-9,]*)/i);
        if (m) return m[0].replace(/Minimum Lumpsum Investment is /i, '').trim();
        // Also scan label-value pairs
        const allEls = Array.from(document.querySelectorAll('*'));
        for (const el of allEls) {
            const txt = (el.innerText || '').trim();
            if (/^min\\.? ?lumpsum$/i.test(txt) || /^minimum lumpsum$/i.test(txt)) {
                const next = el.nextElementSibling;
                if (next) {
                    const val = (next.innerText || '').trim();
                    if (val && val.length < 50) return val;
                }
            }
        }
        return null;
    }

    function findExitLoad() {
        // Actual value is between "Exit load\\n" and "\\nStamp duty" in the section
        const idx = body.indexOf('Exit load, stamp duty and tax');
        if (idx !== -1) {
            const section = body.slice(idx, idx + 1000);
            const m = section.match(/Exit load\\n([\\s\\S]+?)(?:\\nStamp duty|$)/);
            if (m) {
                const val = m[1].trim();
                if (val && !val.toLowerCase().startsWith('a fee payable')) return val;
            }
        }
        // Fallback patterns
        const nilMatch = body.match(/[Ee]xit [Ll]oad[:\\s]*(Nil|NIL|0%)/);
        if (nilMatch) return nilMatch[1];
        return null;
    }

    function findRisk() {
        const levels = [
            'Very High', 'Moderately High', 'High',
            'Moderate', 'Moderately Low', 'Low', 'Very Low'
        ];
        // Check first 2000 chars — risk is prominently shown at top of page
        const top = body.slice(0, 2000);
        for (const lvl of levels) {
            if (top.includes(lvl + ' Risk')) return lvl;
        }
        for (const lvl of levels) {
            if (top.includes(lvl)) return lvl;
        }
        // Full-body fallback
        for (const lvl of levels) {
            if (body.includes(lvl + ' Risk')) return lvl;
        }
        return null;
    }

    return {
        minimum_sip:     findSIP(),
        minimum_lumpsum: findLumpsum(),
        exit_load:       findExitLoad(),
        riskometer:      findRisk(),
    };
}
"""


def extract_all_dynamic_fields(page: Page) -> dict:
    return page.evaluate(_JS_EXTRACT) or {}


def parse_scheme_page(url: str, page: Page) -> SchemeData:
    soup = BeautifulSoup(page.content(), "html.parser")

    scheme_id = url.rstrip('/').split('/')[-1]

    h1 = soup.find('h1')
    scheme_name = h1.text.strip() if h1 else scheme_id.replace('-', ' ').title()

    fund_category = "Equity"
    if "Liquid" in scheme_name:            fund_category = "Liquid"
    elif "ELSS" in scheme_name:            fund_category = "ELSS (Tax Saver)"
    elif "Hybrid" in scheme_name:          fund_category = "Hybrid"
    elif "Arbitrage" in scheme_name:       fund_category = "Arbitrage"
    elif "Large Cap" in scheme_name:       fund_category = "Large Cap"
    elif "Dynamic Asset" in scheme_name:   fund_category = "Dynamic Asset Allocation"

    expense_ratio = extract_metric(soup, ["Expense ratio", "Expense"])
    benchmark     = extract_metric(soup, ["Benchmark", "Index"])

    dynamic     = extract_all_dynamic_fields(page)
    min_sip     = dynamic.get("minimum_sip") or "Not specified"
    min_lumpsum = dynamic.get("minimum_lumpsum") or "Not specified"
    exit_load   = dynamic.get("exit_load") or "Not specified"
    riskometer  = dynamic.get("riskometer") or "Not specified"

    lock_in_period = "Not specified"
    if fund_category == "ELSS (Tax Saver)":
        lock_in_period = "3 years"

    return SchemeData(
        scheme_id=scheme_id,
        scheme_name=scheme_name,
        amc_name="PPFAS Mutual Fund",
        fund_category=fund_category,
        expense_ratio=expense_ratio if expense_ratio != "Not specified" else "Unknown",
        minimum_sip=min_sip,
        minimum_lumpsum=min_lumpsum,
        exit_load=exit_load,
        lock_in_period=lock_in_period,
        riskometer_category=riskometer,
        benchmark_index=benchmark,
        source_url=url
    )

# Fields that must be present and non-empty for a scheme record to be accepted.
# If any of these are missing/invalid during a scheduled run, the record is rejected.
MANDATORY_FIELDS = [
    "scheme_id", "scheme_name", "expense_ratio",
    "minimum_sip", "minimum_lumpsum", "exit_load",
    "riskometer_category", "benchmark_index", "source_url"
]


def validate_scheme(data: SchemeData) -> list:  # type: ignore
    """Return a list of validation error strings. Empty list = valid."""
    errors = []
    d = data.model_dump()
    for field in MANDATORY_FIELDS:
        val = d.get(field, "")
        if not val or val in ("Not specified", "Unknown"):
            errors.append(f"  MISSING: '{field}' = {repr(val)}")
    return errors


def main():
    print("Initiating Phase 1 ETL (Data Ingestion)...")
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for url in SCHEME_URLS:
            print(f"\nScraping {url}...")
            try:
                page.goto(url, timeout=45000, wait_until="networkidle")
                page.wait_for_timeout(3000)

                try:
                    data = parse_scheme_page(url, page)

                    # Validate before accepting — critical for unattended scheduler runs
                    errors = validate_scheme(data)
                    if errors:
                        print(f"  VALIDATION FAILED — skipping {data.scheme_name}:")
                        for e in errors:
                            print(e)
                    else:
                        results.append(data.model_dump())
                        print(f"  Scheme   : {data.scheme_name}")
                        print(f"  SIP      : {data.minimum_sip}")
                        print(f"  Lumpsum  : {data.minimum_lumpsum}")
                        print(f"  Exit Load: {data.exit_load}")
                        print(f"  Risk     : {data.riskometer_category}")
                except Exception as e:
                    print(f"  Parse error: {e}")

            except Exception as e:
                print(f"  Fetch error: {e}")

        browser.close()

    output_dir = os.path.join(os.path.dirname(__file__), "data", "structured")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "ppfas_schemes.json")

    # Only write if we have valid results — never overwrite with empty data
    if not results:
        print("\nETL ABORTED: No valid schemes extracted. Previous JSON preserved.")
        return

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    skipped = len(SCHEME_URLS) - len(results)
    print(f"\nETL Complete! {len(results)}/{len(SCHEME_URLS)} schemes saved to {output_path}")
    if skipped:
        print(f"  WARNING: {skipped} scheme(s) failed validation and were NOT saved.")


if __name__ == "__main__":
    main()
