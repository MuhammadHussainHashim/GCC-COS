# HS codes (layer 2)

## What is here

- `reference/hs2022/harmonized-system.csv`: the HS 2022 code list (97 chapters, 1,229 four-digit headings, 5,613 six-digit subheadings). Source, checksum and license are recorded in `reference/hs2022/SOURCE.json`. The program refuses to run with a changed copy.
- `config/hs_mappings.json`: one entry per product type (for example electronics / Laptop) saying which HS code it gets and why.
- `gcc_cos/hs.py`: reads both files and adds HS columns to records when they are shown or exported. The stored records are not changed.

## What is NOT verified

**Every mapping is marked `proposed_not_verified`.** Each one was written by reading the HS 2022 description; no customs authority, broker or reviewer has confirmed any of them. The dashboard and all exports show this status next to every code.

Other limits:

- A **4-digit code** means only the heading is known. The 6-digit subheading depends on details the source data does not give (for example whether a desktop is an all-in-one).
- **64 of the 1,241 bundled records have no code**, because their product type mixes different goods or no heading is clear. They are listed as `unmapped` with the reason.
- The descriptions are UN Comtrade wording, not the WCO legal text.
- These are international 6-digit codes. Pakistan's 8-digit PCT tariff lines are not included.
- HS 2022 is the edition used. HS 2028 changes are not included.

## Replace a proposed mapping with a verified one

1. In VS Code, open `config/hs_mappings.json`.
2. Find the entry, for example `"subcategory": "Laptop"`.
3. Change `"status"` to `"verified"`, correct `"hs_code"` if needed, and add two lines saying who verified it and what the evidence is:

```json
{"match": {"category": "electronics", "subcategory": "Laptop"}, "hs_code": "847130", "status": "verified",
 "basis": "...",
 "verified_by": "Name and role of the person who checked",
 "verification_evidence": "Ruling number, tariff document and page, or link"}
```

4. Save, then run the tests (**Terminal → Run Task… → GCC-COS: Run tests**). The program rejects a `verified` entry without both extra lines, and rejects any code that is not in the HS 2022 list.

To classify one specific product instead of a whole type, add an entry with `"match": {"product_name": "exact product name"}`. It takes priority over the product-type entry.

## Commands

```powershell
.\.venv\Scripts\python.exe -m gcc_cos hs-lookup smartphones
.\.venv\Scripts\python.exe -m gcc_cos hs-lookup 8471
.\.venv\Scripts\python.exe -m gcc_cos hs-coverage
.\.venv\Scripts\python.exe -m gcc_cos records --products-only --hs 851713
.\.venv\Scripts\python.exe -m gcc_cos export exports/laptops.xlsx --hs 847130
```

`--hs` accepts 2, 4 or 6 digits. In the dashboard, open the **HS codes** tab.
