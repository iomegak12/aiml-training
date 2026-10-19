"""HR policy and compliance facts for the fictional employer Aranya Technologies.

Each policy is a plain dict consumed by ``builders.hr_policy``. Body text is
written here (policy wording *is* the fact), and every policy carries its own
``qa`` list whose ``evidence`` strings are copied verbatim from the text so the
golden Q&A set can be verified against the rendered PDF.

Two policies (Leave, Travel & Expense) exist in a current and a superseded
version built from the same function with different numbers -- the
version-conflict trap for RAG demonstrations.

Statutory references are illustrative teaching material, not legal advice.
"""

from __future__ import annotations

from data_generation.models import Bullets, Paragraph, Table

COMPANY = {
    "name": "Aranya Technologies Pvt. Ltd.",
    "short": "Aranya",
    "cin": "U72900KA2011PTC058812",
    "address": "Aranya Tech Park, 42 Outer Ring Road, Bellandur, Bengaluru, Karnataka 560103",
    "hr_email": "hr.helpdesk@aranya.example",
    "hrms": "Aranya PeopleHub",
    "hr_extension": "4040",
}

GRADES = [
    ("L1", "Associate"),
    ("L2", "Senior Associate"),
    ("L3", "Lead / Specialist"),
    ("L4", "Manager"),
    ("L5", "Senior Manager"),
    ("L6", "Director"),
    ("L7", "Vice President and above"),
]


def _qa(question, answer, evidence, qtype="factual", difficulty="easy"):
    return {"question": question, "answer": answer, "evidence": evidence, "type": qtype, "difficulty": difficulty}


# ---------------------------------------------------------------------------
# Leave Policy (versioned)
# ---------------------------------------------------------------------------

LEAVE_V3 = {
    "version": "3.0", "effective_date": "1 April 2025", "el": 21, "el_monthly": "1.75", "cl": 8, "sl": 10,
    "el_carry": 45, "sl_carry": 30, "encash_exit": 30, "encash_service": "allowed for up to 10 days once per calendar year (in December)",
    "paternity": 10, "paternity_window": "6 months", "bereavement": 5, "marriage": 5, "comp_off_days": 60,
    "holidays_fixed": 10, "holidays_optional": 2, "el_notice_days": 7, "sl_cert_days": 2, "approval_days": 2,
    "probation_el": 6, "lwp_max": 30, "sabbatical": True,
}
LEAVE_V2 = {
    "version": "2.0", "effective_date": "1 April 2023", "el": 18, "el_monthly": "1.5", "cl": 7, "sl": 8,
    "el_carry": 30, "sl_carry": 24, "encash_exit": 20, "encash_service": "not permitted",
    "paternity": 5, "paternity_window": "3 months", "bereavement": 3, "marriage": 3, "comp_off_days": 30,
    "holidays_fixed": 9, "holidays_optional": 2, "el_notice_days": 10, "sl_cert_days": 3, "approval_days": 3,
    "probation_el": 3, "lwp_max": 30, "sabbatical": False,
}


def _leave_policy(v: dict, current: bool) -> dict:
    total_holidays = v["holidays_fixed"] + v["holidays_optional"]
    entitlement = Table(
        header=["Leave type", "Annual entitlement", "Credit / accrual", "Carry forward", "Key conditions"],
        rows=[
            ["Earned Leave (EL)", f"{v['el']} days", f"{v['el_monthly']} days per month", f"Up to {v['el_carry']} days",
             f"Apply {v['el_notice_days']} days in advance for more than 3 days"],
            ["Casual Leave (CL)", f"{v['cl']} days", "Credited on 1 January", "Lapses on 31 December", "Maximum 3 days at a time"],
            ["Sick Leave (SL)", f"{v['sl']} days", "Credited on 1 January", f"Up to {v['sl_carry']} days",
             f"Medical certificate for more than {v['sl_cert_days']} consecutive days"],
            ["Maternity Leave", "26 weeks", "As per statute", "Not applicable", "12 weeks from the third child onwards"],
            ["Paternity Leave", f"{v['paternity']} working days", "Per event", "Not applicable",
             f"To be availed within {v['paternity_window']} of the birth"],
            ["Bereavement Leave", f"{v['bereavement']} working days", "Per event", "Not applicable", "Immediate family members"],
            ["Marriage Leave", f"{v['marriage']} working days", "Once in service", "Not applicable", "Own marriage only"],
        ],
        col_widths=[0.2, 0.17, 0.2, 0.17, 0.26],
        caption=f"Table 1: Leave entitlements under Leave Policy v{v['version']}",
    )
    body = [
        ("Leave Year and Holidays",
         "The leave year at Aranya runs from 1 January to 31 December. Leave balances are maintained in Aranya PeopleHub, "
         "which is the single source of truth for every employee's entitlement, usage and balance.",
         [Paragraph(f"The company declares {total_holidays} paid holidays each calendar year: {v['holidays_fixed']} fixed "
                    f"national and regional holidays and {v['holidays_optional']} optional (restricted) holidays chosen by the "
                    "employee from the published list. The holiday calendar is released every December for the following year.")]),
        ("Leave Entitlements",
         "All confirmed full-time employees are eligible for the leave types summarised below. Part-time employees receive a "
         "pro-rated entitlement based on their contracted hours.",
         [entitlement,
          Paragraph(f"Employees on probation accrue Earned Leave from the date of joining but may avail a maximum of "
                    f"{v['probation_el']} days of EL before confirmation."),
          Paragraph(f"Earned Leave encashment at the time of separation is limited to {v['encash_exit']} days. "
                    f"Encashment of EL during service is {v['encash_service']}.")]),
        ("Statutory and Special Leave",
         "Certain leave types are governed by Indian law and are always applied in line with the applicable statute, even "
         "where this policy is silent.",
         [Bullets([
             "Maternity leave is granted as per the Maternity Benefit Act, 1961 (as amended in 2017): 26 weeks for the first two "
             "children and 12 weeks thereafter, of which up to 8 weeks may be taken before the expected delivery date.",
             "Adoption leave of 12 weeks is available to a woman employee who legally adopts a child below the age of 3 months, "
             "and 12 weeks to a commissioning mother.",
             "Leave for miscarriage or medical termination of pregnancy is 6 weeks from the date of the event.",
             f"Compensatory off (comp off) is earned for approved work on a weekly off or holiday and must be availed within "
             f"{v['comp_off_days']} days, failing which it lapses.",
             f"Leave Without Pay (LWP) of up to {v['lwp_max']} days in a leave year may be approved by the HR Business Partner "
             "once all paid leave is exhausted.",
         ])]),
    ]
    if v["sabbatical"]:
        body.append(("Sabbatical",
                     "Aranya supports employees who wish to take an extended break from work for higher education, "
                     "caregiving or personal development.",
                     [Paragraph("Employees with 5 or more years of continuous service may apply for an unpaid sabbatical "
                                "of 3 to 6 months."),
                      Paragraph("Sabbatical requests require approval from the department head and the Chief People Officer and "
                                "must be submitted at least 60 days before the proposed start date. Medical insurance continues "
                                "during the sabbatical; other benefits are suspended.")]))

    supersedes = None if not current else "Leave Policy v2.0 (effective 1 April 2023)"
    superseded_by = None if current else "Leave Policy v3.0 (effective 1 April 2025)"
    revisions = [("1.0", "1 April 2019", "Initial release."),
                 ("2.0", "1 April 2023", "Introduced optional holidays and online leave approval in PeopleHub.")]
    if current:
        revisions.append(("3.0", "1 April 2025",
                          "EL increased from 18 to 21 days, EL carry forward raised from 30 to 45 days, paternity leave raised "
                          "from 5 to 10 working days, sabbatical introduced."))

    qa = [
        _qa("How many days of earned leave does an Aranya employee get per year?" if current else
            "Under the superseded Leave Policy v2.0 (2023), how many days of earned leave did an employee get per year?",
            f"{v['el']} days per year" + (" (Leave Policy v3.0, effective 1 April 2025; the superseded v2.0 allowed 18 days)."
                                          if current else " under the superseded v2.0; the current v3.0 allows 21 days."),
            ["Earned Leave (EL)", f"{v['el']} days"], "version_conflict", "medium"),
        _qa("What is the maximum earned leave that can be carried forward to the next year?" if current else
            "What was the earned leave carry-forward limit in Leave Policy v2.0?",
            f"Up to {v['el_carry']} days" + (" (v3.0; the superseded v2.0 limit was 30 days)." if current else " under v2.0 (now 45 days in v3.0)."),
            [f"Up to {v['el_carry']} days"], "version_conflict", "medium"),
        _qa("How many working days of paternity leave are allowed, and within what period must it be availed?" if current else
            "How much paternity leave did the 2023 Leave Policy v2.0 provide?",
            f"{v['paternity']} working days, to be availed within {v['paternity_window']} of the birth.",
            [f"{v['paternity']} working days", f"within {v['paternity_window']} of the birth"], "version_conflict", "medium"),
    ]
    if current:
        qa += [
            _qa("When is a medical certificate required for sick leave?",
                "For sick leave of more than 2 consecutive days.",
                ["Medical certificate for more than 2 consecutive days"], "table_lookup"),
            _qa("Who is eligible for a sabbatical and how long can it be?",
                "Employees with 5 or more years of continuous service may take an unpaid sabbatical of 3 to 6 months.",
                ["5 or more years of continuous service", "3 to 6 months"], "factual", "easy"),
            _qa("Within how many days must a compensatory off be availed?",
                "Within 60 days, failing which it lapses.",
                ["must be availed within 60 days"], "factual", "easy"),
            _qa("How many weeks of maternity leave apply from the third child onwards?",
                "12 weeks.", ["12 weeks from the third child onwards"], "table_lookup", "easy"),
        ]
    else:
        qa.append(_qa("How many paid holidays did the superseded Leave Policy v2.0 declare per year?",
                      "11 paid holidays (9 fixed and 2 optional) under v2.0; the current v3.0 declares 12.",
                      ["declares 11 paid holidays"], "version_conflict", "hard"))

    return {
        "policy_id": "HR-POL-001",
        "title": "Leave Policy",
        "version": v["version"],
        "effective_date": v["effective_date"],
        "status": "current" if current else "superseded",
        "owner": "Head - Human Resources Operations",
        "approver": "Chief People Officer",
        "review_cycle": "Annual",
        "supersedes": supersedes,
        "superseded_by": superseded_by,
        "purpose": "This policy sets out the types of leave available to employees of Aranya Technologies, how leave is earned "
                   "and applied for, and the rules for carry forward and encashment. It aims to help employees rest, recover "
                   "and attend to personal commitments while allowing teams to plan work predictably.",
        "scope": "The policy applies to all full-time and part-time employees on the rolls of Aranya Technologies Pvt. Ltd. in "
                 "India, including employees on probation. Interns, consultants and contract staff engaged through vendors are "
                 "governed by their engagement terms.",
        "definitions": [
            ("Leave year", "The calendar year from 1 January to 31 December."),
            ("Working day", "Any day other than a weekly off or a declared holiday at the employee's base location."),
            ("Immediate family", "Spouse, children, parents, parents-in-law and siblings."),
            ("HRBP", "The HR Business Partner assigned to the employee's business unit."),
        ],
        "body": body,
        "procedure": [
            "Apply for leave in Aranya PeopleHub under Leave > Apply, selecting the leave type and dates.",
            f"The reporting manager approves or rejects the request within {v['approval_days']} working days; pending requests "
            "escalate automatically to the skip-level manager.",
            "For unplanned sick leave, inform the manager by phone or message before 10:00 AM on the first day and apply in "
            "PeopleHub within 2 working days of returning.",
            "Upload supporting documents (medical certificate, birth certificate, adoption order) in PeopleHub where required.",
            "Leave taken without approval is treated as unauthorised absence and recorded as Leave Without Pay.",
        ],
        "exceptions": "Any deviation from this policy, including advance leave beyond the accrued balance, requires written "
                      "approval from the HRBP and the department head. Statutory entitlements always prevail over this policy.",
        "faqs": [
            ("Can I combine Casual Leave with Earned Leave?", "No. Casual Leave cannot be prefixed or suffixed to Earned Leave; "
             "Sick Leave may be combined with Earned Leave when supported by a medical certificate."),
            ("Do weekends falling within a leave period count as leave?", "No. Weekly offs and holidays within an approved leave "
             "period are not counted against the leave balance."),
            ("What happens to my Casual Leave at year end?", "Unused Casual Leave lapses on 31 December and is not encashed."),
            ("Is Leave Without Pay deducted from salary?", "Yes. LWP days are deducted from gross salary on a per-day basis "
             "for the month in which the leave is taken."),
        ],
        "revisions": revisions,
        "related": ["Attendance, Working Hours and Overtime Policy (HR-POL-009)",
                    "Separation, Notice Period and Full and Final Settlement Policy (HR-POL-013)"],
        "qa": qa,
    }


# ---------------------------------------------------------------------------
# Travel & Expense Claims Policy (versioned)
# ---------------------------------------------------------------------------

TRAVEL_V4 = {
    "version": "4.0", "effective_date": "1 January 2026",
    "hotel": {"X": ("8,000", "11,000"), "Y": ("5,500", "8,000"), "Z": ("4,000", "6,000")},
    "per_diem": {"X": "3,500", "Y": "2,500", "Z": "1,800"},
    "intl_per_diem": [("United States", "USD 75"), ("United Kingdom", "GBP 60"), ("Eurozone countries", "EUR 65"),
                      ("Singapore", "SGD 95"), ("All other countries", "USD 60")],
    "car_km": "12", "bike_km": "5", "local_cab": "1,500", "submit_days": 30, "receipt_above": "500",
    "reimburse_days": 10, "advance_pct": 75, "advance_settle_days": 15,
    "intl_l4_l5": "Premium economy", "intl_l6": "Business class",
}
TRAVEL_V3 = {
    "version": "3.0", "effective_date": "1 April 2024",
    "hotel": {"X": ("6,500", "9,000"), "Y": ("4,500", "6,500"), "Z": ("3,200", "4,800")},
    "per_diem": {"X": "2,800", "Y": "2,000", "Z": "1,500"},
    "intl_per_diem": [("United States", "USD 60"), ("United Kingdom", "GBP 50"), ("Eurozone countries", "EUR 55"),
                      ("Singapore", "SGD 80"), ("All other countries", "USD 50")],
    "car_km": "9", "bike_km": "4", "local_cab": "1,000", "submit_days": 45, "receipt_above": "300",
    "reimburse_days": 15, "advance_pct": 60, "advance_settle_days": 30,
    "intl_l4_l5": "Economy", "intl_l6": "Premium economy (L6); business class (L7)",
}


def _travel_policy(v: dict, current: bool) -> dict:
    h, pd = v["hotel"], v["per_diem"]
    domestic = Table(
        header=["City tier", "Hotel cap per night (L1 to L3)", "Hotel cap per night (L4 to L5)", "Daily per diem (all grades)"],
        rows=[[f"Tier {t}", f"Rs. {h[t][0]}", f"Rs. {h[t][1]}", f"Rs. {pd[t]}"] for t in ("X", "Y", "Z")],
        col_widths=[0.16, 0.28, 0.28, 0.28],
        caption=f"Table 1: Domestic accommodation and per diem limits (v{v['version']})",
    )
    travel_class = Table(
        header=["Mode", "L1 to L3", "L4 to L5", "L6 and above"],
        rows=[
            ["Domestic air", "Economy", "Economy", "Economy; premium economy for flights over 3 hours"],
            ["International air (over 6 hours)", "Economy", v["intl_l4_l5"], v["intl_l6"]],
            ["Train", "AC 2-tier", "AC First Class", "AC First Class"],
            ["Own vehicle (per km)", f"Car Rs. {v['car_km']}, two-wheeler Rs. {v['bike_km']}", "Same as L1 to L3", "Same as L1 to L3"],
        ],
        col_widths=[0.25, 0.22, 0.22, 0.31],
        caption="Table 2: Travel class entitlement by grade",
    )
    intl = Table(header=["Destination", "Daily per diem"], rows=[list(r) for r in v["intl_per_diem"]],
                 col_widths=[0.5, 0.5], caption="Table 3: International per diem (meals and incidentals)")
    body = [
        ("City Classification",
         "Domestic limits depend on the tier of the destination city. The tiering follows the company's cost-of-living "
         "classification and is reviewed every two years.",
         [Bullets([
             "Tier X: Mumbai, Delhi NCR, Bengaluru, Chennai, Kolkata, Hyderabad, Pune and Ahmedabad.",
             "Tier Y: Jaipur, Lucknow, Kochi, Coimbatore, Indore, Chandigarh, Bhubaneswar, Nagpur, Visakhapatnam and Mysuru.",
             "Tier Z: all other cities and towns in India.",
         ])]),
        ("Accommodation and Per Diem",
         "Employees should book accommodation through the company travel desk at empanelled hotels wherever available. The "
         "per diem covers meals, tips and minor incidentals and is paid without bills.",
         [domestic,
          Paragraph("Employees in grade L6 and above may stay at empanelled hotels at actual cost. If an employee stays with "
                    "friends or relatives instead of a hotel, a lodging allowance of 25% of the applicable hotel cap is payable.")]),
        ("Travel Class and Conveyance",
         "Air travel must be booked at least 7 days in advance through the travel desk, choosing the lowest fare available "
         "within one hour of the preferred departure time.",
         [travel_class,
          Paragraph(f"Local conveyance at the destination by taxi or app-based cab is reimbursed up to Rs. {v['local_cab']} per day. "
                    f"Receipts are mandatory for any single expense above Rs. {v['receipt_above']}.")]),
        ("International Travel",
         "International travel requires pre-approval from the department head and the Chief Financial Officer and must be "
         "booked at least 21 days in advance.",
         [intl,
          Paragraph("Travel insurance is arranged by the travel desk for every international trip. Visa fees, forex card "
                    "charges and mandatory vaccinations are reimbursed at actuals.")]),
        ("Non-Reimbursable Expenses",
         None,
         [Bullets(["Alcoholic beverages, tobacco and minibar charges.",
                   "Traffic fines, parking penalties and late check-out charges caused by personal choice.",
                   "Personal entertainment, spa, gym and in-room movies.",
                   "Class upgrades not permitted by Table 2, and loss of personal belongings.",
                   "Laundry charges for trips shorter than 3 nights."])]),
    ]
    revisions = [("1.0", "1 April 2018", "Initial release."),
                 ("2.0", "1 April 2021", "Added international per diem and online claims."),
                 ("3.0", "1 April 2024", "Revised hotel caps and introduced city tiers X, Y and Z.")]
    if current:
        revisions.append(("4.0", "1 January 2026", "Hotel caps and per diem increased, mileage rate raised to Rs. 12 per km, "
                                                   "claim window reduced from 45 to 30 days, advance limit raised to 75%."))
    qa = [
        _qa("What is the daily per diem for travel to a Tier X city?" if current else
            "What was the Tier X daily per diem under Travel Policy v3.0 (2024)?",
            f"Rs. {pd['X']} per day" + (" (v4.0, effective 1 January 2026; the superseded v3.0 allowed Rs. 2,800)." if current
                                        else " under the superseded v3.0; the current v4.0 allows Rs. 3,500."),
            ["Tier X", f"Rs. {pd['X']}"], "version_conflict", "medium"),
        _qa("Within how many days of completing a trip must an expense claim be submitted?" if current else
            "What was the claim submission window in Travel Policy v3.0?",
            f"Within {v['submit_days']} days of completing the trip" + (" (v4.0; v3.0 allowed 45 days)." if current else " under v3.0 (now 30 days)."),
            [f"within {v['submit_days']} days of completing the trip"], "version_conflict", "medium"),
        _qa("What is the mileage reimbursement rate for using one's own car?" if current else
            "What car mileage rate applied under Travel Policy v3.0?",
            f"Rs. {v['car_km']} per km for a car and Rs. {v['bike_km']} per km for a two-wheeler.",
            [f"Car Rs. {v['car_km']}, two-wheeler Rs. {v['bike_km']}"], "version_conflict", "medium"),
    ]
    if current:
        qa += [
            _qa("What is the hotel cap per night for an L4 manager travelling to a Tier Y city?",
                "Rs. 8,000 per night.", ["Tier Y", "Rs. 8,000"], "table_lookup", "medium"),
            _qa("What is the international per diem for the United Kingdom?", "GBP 60 per day.",
                ["United Kingdom", "GBP 60"], "table_lookup", "easy"),
            _qa("Is Pune a Tier X or Tier Y city for travel claims?", "Pune is a Tier X city.",
                ["Tier X: Mumbai, Delhi NCR, Bengaluru, Chennai, Kolkata, Hyderabad, Pune and Ahmedabad."], "factual", "easy"),
            _qa("Are laundry charges reimbursable for a two-night trip?",
                "No. Laundry charges are not reimbursable for trips shorter than 3 nights.",
                ["Laundry charges for trips shorter than 3 nights."], "factual", "medium"),
        ]
    return {
        "policy_id": "HR-POL-002",
        "title": "Travel and Expense Claims Policy",
        "version": v["version"],
        "effective_date": v["effective_date"],
        "status": "current" if current else "superseded",
        "owner": "Head - Finance Operations",
        "approver": "Chief Financial Officer",
        "review_cycle": "Every 2 years",
        "supersedes": "Travel and Expense Claims Policy v3.0 (effective 1 April 2024)" if current else None,
        "superseded_by": None if current else "Travel and Expense Claims Policy v4.0 (effective 1 January 2026)",
        "purpose": "This policy defines how employees travel on company business and how business expenses are claimed and "
                   "reimbursed. It balances employee comfort and safety with responsible use of company funds.",
        "scope": "It applies to all employees of Aranya Technologies travelling within India or overseas for business "
                 "purposes, and to candidates and consultants whose travel is approved by the company.",
        "definitions": [
            ("Per diem", "A fixed daily allowance for meals and incidentals, paid without bills."),
            ("Travel desk", "The company's in-house booking team, reachable at travel@aranya.example."),
            ("Empanelled hotel", "A hotel with a negotiated corporate rate listed on the travel portal."),
            ("Trip completion", "The date the employee returns to the base location."),
        ],
        "body": body,
        "procedure": [
            "Raise a travel request in Aranya PeopleHub under Travel > New Request with purpose, dates and estimated cost.",
            f"If required, request a travel advance of up to {v['advance_pct']}% of the estimated cost.",
            f"Submit the expense claim with receipts within {v['submit_days']} days of completing the trip. Claims submitted "
            "more than 90 days after the trip are rejected.",
            "The reporting manager reviews the claim within 5 working days, after which Finance audits it.",
            f"Approved claims are reimbursed within {v['reimburse_days']} working days of Finance approval. Any advance must be "
            f"settled within {v['advance_settle_days']} days of return.",
        ],
        "exceptions": "Expenses above the limits in this policy are reimbursed only with prior written approval from the "
                      "department head. Exceptions above Rs. 50,000 per trip also require approval from the Chief Financial Officer.",
        "faqs": [
            ("Do I need receipts for the per diem?", "No. The per diem is paid without bills. Receipts are needed for hotel, "
             "travel and other actual expenses."),
            ("Can I book my own flight and claim it?", "Only if the travel desk cannot book it, and the fare must not exceed the "
             "lowest fare shown on the travel portal at the time of booking."),
            ("What if I lose a receipt?", "Submit a signed self-declaration in PeopleHub. Self-declarations are allowed for at most "
             "two expenses per trip and are reviewed by Finance."),
            ("Are client dinners covered under this policy?", "Business entertainment must also comply with the Anti-Bribery and "
             "Anti-Corruption Policy (HR-POL-012) and requires manager pre-approval."),
        ],
        "revisions": revisions,
        "related": ["Anti-Bribery and Anti-Corruption Policy (HR-POL-012)", "Code of Conduct and Ethics (HR-POL-004)"],
        "qa": qa,
    }


# ---------------------------------------------------------------------------
# Single-version policies
# ---------------------------------------------------------------------------

MEDICAL = {
    "policy_id": "HR-POL-003",
    "title": "Medical Reimbursement and Group Health Insurance Policy",
    "version": "2.1",
    "effective_date": "1 January 2026",
    "owner": "Head - Total Rewards",
    "approver": "Chief People Officer",
    "review_cycle": "Annual, aligned to insurance renewal",
    "purpose": "This policy explains the health and protection benefits that Aranya provides to employees and their families, "
               "including group health insurance, outpatient reimbursement, preventive health checks and life cover.",
    "scope": "It applies to all confirmed and probationary full-time employees in India and their enrolled dependants. "
             "Benefits for fixed-term employees are as stated in their appointment letters.",
    "definitions": [
        ("GMC", "Group Mediclaim Cover, the company-paid hospitalisation insurance."),
        ("TPA", "Third Party Administrator, HealthBridge TPA Services Pvt. Ltd., which processes claims."),
        ("Sum insured", "The maximum amount payable under the policy in a policy year for the family."),
        ("Policy year", "1 January to 31 December."),
    ],
    "body": [
        ("Group Health Insurance",
         "Aranya provides cashless hospitalisation cover through Suraksha General Insurance Co. Ltd., with claims "
         "administered by HealthBridge TPA Services Pvt. Ltd.",
         [Table(header=["Benefit", "Coverage"], col_widths=[0.4, 0.6], caption="Table 1: Group Mediclaim Cover summary", rows=[
             ["Sum insured", "Rs. 5,00,000 per family (floater)"],
             ["Covered members", "Employee, spouse and up to 2 children up to age 25"],
             ["Room rent", "Up to 2% of sum insured per day (Rs. 10,000)"],
             ["ICU charges", "Up to 4% of sum insured per day (Rs. 20,000)"],
             ["Pre and post hospitalisation", "30 days before and 60 days after admission"],
             ["Maternity", "Rs. 75,000 normal delivery; Rs. 1,00,000 caesarean delivery"],
             ["Pre-existing diseases", "Covered from day one"],
             ["Co-payment", "Nil for employee family; 20% for parents"],
         ])]),
        ("Parental Cover",
         "Employees may enrol parents or parents-in-law (not both sets) under a separate parental policy.",
         [Paragraph("The parental sum insured is Rs. 3,00,000 per policy. The premium is paid by the employee through monthly "
                    "payroll deduction. Enrolment is allowed within 30 days of joining or during the annual enrolment window "
                    "in January each year.")]),
        ("Outpatient (OPD) Reimbursement",
         "Outpatient expenses not requiring hospitalisation can be reimbursed through the OPD benefit.",
         [Bullets(["Annual OPD limit of Rs. 15,000 per financial year per employee.",
                   "Covers doctor consultations, prescribed medicines, diagnostics, dental treatment and physiotherapy.",
                   "Spectacles or contact lenses up to Rs. 5,000 once in 2 years, within the OPD limit.",
                   "Claims must be submitted in PeopleHub by 15 March for the financial year ending 31 March."])]),
        ("Preventive Health and Protection",
         None,
         [Bullets(["Annual health check-up worth Rs. 3,500, free for employees aged 35 years and above.",
                   "Group Term Life insurance of 3 times annual fixed CTC, with a minimum cover of Rs. 10,00,000.",
                   "Group Personal Accident cover of 3 times annual fixed CTC, covering accidental death and disability.",
                   "Confidential Employee Assistance Programme counselling, 6 free sessions per year per family member."])]),
    ],
    "procedure": [
        "For planned hospitalisation, raise a cashless pre-authorisation request with the TPA at least 72 hours before admission.",
        "For emergency hospitalisation, the hospital or family must inform the TPA within 24 hours of admission.",
        "For reimbursement claims (non-network hospitals), submit original bills and the discharge summary within 30 days of discharge.",
        "Track claim status on the HealthBridge portal or contact healthdesk@aranya.example for escalation.",
    ],
    "exceptions": "Treatments excluded by the insurer (for example cosmetic surgery and non-allopathic treatment beyond the "
                  "AYUSH limit) are not reimbursed by the company. Exceptional medical assistance may be considered by the "
                  "Chief People Officer on compassionate grounds.",
    "faqs": [
        ("Can I add my newborn child mid-year?", "Yes. Newborns are covered from day one; inform HR within 30 days of birth."),
        ("Does the cover continue after I resign?", "Cover ends on the last working day. Employees may port to an individual "
         "policy with the insurer within 30 days."),
        ("Is the OPD limit carried forward?", "No. Unused OPD balance lapses at the end of each financial year."),
        ("Can I cover both my parents and parents-in-law?", "No. Only one set of parents can be enrolled under the parental policy."),
    ],
    "revisions": [("1.0", "1 January 2021", "Initial release."),
                  ("2.0", "1 January 2024", "Sum insured raised to Rs. 5,00,000; OPD benefit introduced."),
                  ("2.1", "1 January 2026", "OPD limit raised to Rs. 15,000; spectacles included.")],
    "related": ["Leave Policy (HR-POL-001)", "Code of Conduct and Ethics (HR-POL-004)"],
    "qa": [
        _qa("What is the family floater sum insured under the group health insurance?", "Rs. 5,00,000 per family (floater).",
            ["Sum insured", "Rs. 5,00,000 per family (floater)"], "table_lookup"),
        _qa("What is the maternity benefit for a caesarean delivery?", "Rs. 1,00,000.",
            ["Rs. 1,00,000 caesarean delivery"], "table_lookup"),
        _qa("What is the annual OPD reimbursement limit?", "Rs. 15,000 per financial year per employee.",
            ["Annual OPD limit of Rs. 15,000 per financial year per employee."]),
        _qa("How soon must the TPA be informed of an emergency hospitalisation?", "Within 24 hours of admission.",
            ["inform the TPA within 24 hours of admission"], "procedural"),
        _qa("What co-payment applies to parents' claims?", "20% co-payment for parents; nil for the employee family.",
            ["Nil for employee family; 20% for parents"], "table_lookup", "medium"),
        _qa("Who is eligible for the free annual health check-up and what is it worth?",
            "Employees aged 35 years and above; the check-up is worth Rs. 3,500.",
            ["Annual health check-up worth Rs. 3,500, free for employees aged 35 years and above."], "factual", "medium"),
    ],
}

CODE_OF_CONDUCT = {
    "policy_id": "HR-POL-004",
    "title": "Code of Conduct and Ethics",
    "version": "5.0",
    "effective_date": "1 July 2025",
    "owner": "Chief Ethics and Compliance Officer",
    "approver": "Board of Directors",
    "review_cycle": "Every 2 years",
    "purpose": "The Code of Conduct describes the standards of integrity, respect and professionalism expected of everyone "
               "who works at or with Aranya. It translates the company's values into practical expectations for everyday "
               "decisions and protects the trust of customers, colleagues and shareholders.",
    "scope": "The Code applies to all employees, directors, interns and trainees of Aranya Technologies, and to consultants and "
             "contractors while they work on company premises or company assignments.",
    "definitions": [
        ("Conflict of interest", "A situation where a personal interest could interfere with the employee's duty to Aranya."),
        ("Relative", "Spouse, parent, child, sibling or any person living in the same household."),
        ("Ethics Committee", "The committee chaired by the Chief Ethics and Compliance Officer that oversees this Code."),
    ],
    "body": [
        ("Conflicts of Interest",
         "Employees must avoid situations where personal interests conflict, or appear to conflict, with the interests of "
         "the company.",
         [Bullets(["Any actual or potential conflict must be declared in PeopleHub within 15 days of it arising.",
                   "Every employee must submit an annual conflict-of-interest declaration by 30 April.",
                   "Outside employment, paid consulting or a directorship in another company requires prior written approval "
                   "from the Chief People Officer.",
                   "Employees must not directly or indirectly supervise a relative or influence a relative's hiring, pay or rating."])]),
        ("Gifts and Entertainment",
         "Modest gifts can build goodwill, but they must never influence, or appear to influence, a business decision.",
         [Paragraph("Employees may accept a gift with a value not exceeding Rs. 2,000 from a business partner, no more than "
                    "twice a year from the same source. Cash, gift cards and cash equivalents must never be accepted. Any gift "
                    "above the limit must be politely declined or handed to the Compliance team and recorded in the Gift "
                    "Register within 7 days. Giving gifts is governed by the Anti-Bribery and Anti-Corruption Policy (HR-POL-012).")]),
        ("Workplace Behaviour",
         "Aranya is committed to a respectful, inclusive and safe workplace free from discrimination, bullying and harassment.",
         [Bullets(["Treat colleagues, customers and partners with dignity regardless of gender, caste, religion, disability, "
                   "age, sexual orientation or region.",
                   "Consumption of alcohol or drugs at the workplace is strictly prohibited. Alcohol may be served at company "
                   "events only with prior approval from the Chief People Officer.",
                   "Dress code is business casual from Monday to Thursday and smart casual on Fridays; client-facing roles "
                   "follow the client's dress code.",
                   "Employees must not speak on behalf of Aranya on social media or to the press unless authorised by "
                   "Corporate Communications."])]),
        ("Disciplinary Action",
         "Breaches of this Code are addressed through a fair and documented process proportionate to the seriousness of "
         "the breach.",
         [Table(header=["Stage", "Typical trigger", "Record retained"], col_widths=[0.25, 0.5, 0.25],
                caption="Table 1: Progressive disciplinary framework", rows=[
                    ["Verbal counselling", "Minor first-time lapse", "6 months"],
                    ["Written warning", "Repeated minor lapse or moderate breach", "12 months"],
                    ["Final written warning", "Serious breach or repeat after written warning", "24 months"],
                    ["Suspension pending inquiry", "Alleged gross misconduct", "Permanent"],
                    ["Termination", "Proven gross misconduct", "Permanent"],
                ]),
          Paragraph("An employee suspended pending inquiry receives a subsistence allowance of 50% of wages for the first 90 "
                    "days of suspension and 75% thereafter, as provided under the applicable standing orders.")]),
    ],
    "procedure": [
        "Read the Code during onboarding and acknowledge it in PeopleHub within 15 days of joining.",
        "Re-acknowledge the Code every year during the annual compliance window in April.",
        "Raise questions or concerns with your manager, HRBP or the Ethics Committee at ethics@aranya.example.",
        "Report suspected violations through the channels in the Whistleblower and Grievance Redressal Policy (HR-POL-011).",
    ],
    "exceptions": "No waiver of this Code may be granted to an employee except by the Ethics Committee in writing. Waivers "
                  "for directors or key managerial personnel require Board approval.",
    "faqs": [
        ("A vendor sent me a box of sweets worth Rs. 1,200 during Diwali. Can I keep it?", "Yes. It is below the Rs. 2,000 "
         "limit and is not cash, but you may still share it with your team."),
        ("Can I run a weekend tutoring business?", "Only with prior written approval from the Chief People Officer, and it "
         "must not compete with Aranya or use company resources."),
        ("My cousin has applied to my team. What should I do?", "Declare the relationship and step away from the hiring "
         "decision; the HRBP will assign an independent panel."),
    ],
    "revisions": [("4.0", "1 July 2023", "Added social media guidance."),
                  ("5.0", "1 July 2025", "Updated gift limits and introduced the progressive disciplinary framework.")],
    "related": ["Prevention of Sexual Harassment Policy (HR-POL-005)", "Anti-Bribery and Anti-Corruption Policy (HR-POL-012)"],
    "qa": [
        _qa("What is the maximum value of a gift an employee may accept from a business partner?",
            "Rs. 2,000 per gift, no more than twice a year from the same source.",
            ["value not exceeding Rs. 2,000"], "factual", "easy"),
        _qa("By when must the annual conflict-of-interest declaration be submitted?", "By 30 April every year.",
            ["annual conflict-of-interest declaration by 30 April"]),
        _qa("What subsistence allowance is paid during suspension pending inquiry?",
            "50% of wages for the first 90 days and 75% thereafter.",
            ["subsistence allowance of 50% of wages for the first 90"], "factual", "medium"),
        _qa("How long is a written warning retained on record?", "12 months.",
            ["Written warning", "12 months"], "table_lookup", "medium"),
        _qa("Within how many days of joining must the Code be acknowledged?", "Within 15 days of joining.",
            ["acknowledge it in PeopleHub within 15 days of joining"], "procedural"),
    ],
}

POSH = {
    "policy_id": "HR-POL-005",
    "title": "Prevention of Sexual Harassment (POSH) Policy",
    "version": "3.0",
    "effective_date": "1 January 2025",
    "owner": "Presiding Officer, Internal Committee",
    "approver": "Chief People Officer",
    "review_cycle": "Annual",
    "purpose": "Aranya has zero tolerance for sexual harassment. This policy sets out how the company prevents, prohibits and "
               "redresses sexual harassment at the workplace in line with the Sexual Harassment of Women at Workplace "
               "(Prevention, Prohibition and Redressal) Act, 2013 and its Rules.",
    "scope": "The policy covers all employees, interns, trainees, consultants, visitors and contract workers at every Aranya "
             "location, client site, company event, business trip and in any virtual workplace including chat and video calls.",
    "definitions": [
        ("Sexual harassment", "Any unwelcome act or behaviour of a sexual nature, whether physical, verbal, non-verbal or "
                              "digital, including those listed in Section 2(n) of the Act."),
        ("Internal Committee (IC)", "The committee constituted under Section 4 of the Act to receive and inquire into complaints."),
        ("Aggrieved woman", "A woman who alleges she has been subjected to sexual harassment at the workplace."),
        ("Respondent", "The person against whom a complaint has been made."),
    ],
    "body": [
        ("Internal Committee",
         "Aranya has constituted an Internal Committee at each office with 10 or more employees. Its composition follows "
         "Section 4 of the Act.",
         [Bullets(["Presiding Officer: a woman employed at a senior level in the organisation.",
                   "At least 2 members from among employees committed to the cause of women or with experience in social "
                   "work or legal knowledge.",
                   "One external member from a non-governmental organisation or association committed to the cause of women.",
                   "At least one half of the members are women.",
                   "Members hold office for a period not exceeding 3 years."]),
          Paragraph("The Internal Committee can be reached confidentially at ic@aranya.example. Member names are displayed on "
                    "notice boards at every office and on the PeopleHub home page.")]),
        ("Timelines",
         "The Act prescribes strict timelines so that complaints are resolved fairly and quickly.",
         [Table(header=["Step", "Timeline"], col_widths=[0.6, 0.4], caption="Table 1: POSH complaint timelines", rows=[
             ["Filing a written complaint", "Within 3 months of the incident (or the last incident in a series)"],
             ["Extension of filing time by the IC", "Up to a further 3 months, with reasons recorded"],
             ["Copy of complaint sent to respondent", "Within 7 working days"],
             ["Respondent's reply", "Within 10 working days of receiving the complaint"],
             ["Completion of inquiry", "Within 90 days"],
             ["Inquiry report to employer", "Within 10 days of completing the inquiry"],
             ["Employer action on recommendations", "Within 60 days of receiving the report"],
             ["Appeal against recommendations", "Within 90 days"],
         ])]),
        ("Conciliation and Interim Relief",
         None,
         [Paragraph("At the request of the aggrieved woman, the IC may attempt conciliation before starting an inquiry, "
                    "provided that no monetary settlement is made the basis of conciliation. During the inquiry, the IC may "
                    "recommend interim relief such as transfer of either party, leave of up to 3 months for the aggrieved "
                    "woman in addition to her regular leave, or restraining the respondent from reporting on her work.")]),
        ("Confidentiality and False Complaints",
         None,
         [Paragraph("The identity of the complainant, respondent and witnesses, and the contents of the inquiry, must not be "
                    "published or disclosed. Breach of confidentiality attracts disciplinary action. A complaint found to be "
                    "malicious or based on knowingly false evidence may lead to action against the complainant; however, "
                    "inability to prove a complaint does not by itself make it false.")]),
    ],
    "procedure": [
        "Submit a written complaint to any IC member or at ic@aranya.example; the IC will help a complainant who cannot write.",
        "The IC acknowledges the complaint and sends a copy to the respondent within 7 working days.",
        "Both parties are heard, may present witnesses and receive a copy of the other party's statements.",
        "The IC submits its findings and recommendations to the employer, which acts on them within 60 days.",
        "Aranya files an annual report on POSH cases with the District Officer as required by the Act.",
    ],
    "exceptions": "There are no exceptions to this policy. Where a complaint involves the Chief Executive Officer or a director, "
                  "the IC reports its findings directly to the Board.",
    "faqs": [
        ("Can I complain about harassment that happened on a video call?", "Yes. The policy covers virtual workplaces, "
         "including chat and video calls."),
        ("Can a colleague file a complaint on my behalf?", "Yes, where the aggrieved woman is unable to do so because of "
         "physical or mental incapacity, or with her written consent, as permitted under the Rules."),
        ("Is POSH training mandatory?", "Yes. All employees complete POSH awareness training within 30 days of joining and "
         "every year thereafter; IC members receive additional training."),
    ],
    "revisions": [("2.0", "1 January 2022", "Extended scope to virtual workplaces."),
                  ("3.0", "1 January 2025", "Updated timelines table and interim relief options.")],
    "related": ["Code of Conduct and Ethics (HR-POL-004)", "Whistleblower and Grievance Redressal Policy (HR-POL-011)"],
    "qa": [
        _qa("Within what time must a POSH complaint be filed?",
            "Within 3 months of the incident (or the last incident in a series), extendable by a further 3 months by the IC.",
            ["Within 3 months of the incident"], "table_lookup"),
        _qa("How long does the Internal Committee have to complete a POSH inquiry?", "90 days.",
            ["Completion of inquiry", "Within 90 days"], "table_lookup"),
        _qa("Within how many days must the employer act on the IC's recommendations?", "Within 60 days of receiving the report.",
            ["Within 60 days of receiving the report"], "table_lookup", "medium"),
        _qa("Who must chair the Internal Committee?", "A woman employed at a senior level in the organisation (the Presiding Officer).",
            ["Presiding Officer: a woman employed at a senior level in the organisation."]),
        _qa("Can a monetary settlement be the basis of conciliation under the POSH policy?", "No.",
            ["no monetary settlement is made the basis of conciliation"], "factual", "medium"),
    ],
}

HYBRID = {
    "policy_id": "HR-POL-006",
    "title": "Hybrid Work and Work From Home Policy",
    "version": "2.0",
    "effective_date": "1 October 2025",
    "owner": "Head - Workplace Experience",
    "approver": "Chief People Officer",
    "review_cycle": "Annual",
    "purpose": "This policy describes how Aranya combines in-office collaboration with the flexibility of remote work. It sets "
               "clear expectations on office attendance, availability, allowances and information security for hybrid working.",
    "scope": "It applies to employees in roles designated as hybrid-eligible. Roles that require physical presence, such as "
             "lab engineers, facilities staff and front-desk teams, are excluded.",
    "definitions": [
        ("Anchor days", "Tuesday, Wednesday and Thursday, when teams are expected to be in the office together."),
        ("Core hours", "11:00 AM to 4:00 PM IST, when all employees must be available online."),
        ("Work from Anywhere (WFA)", "Working temporarily from a location in India other than the home city."),
    ],
    "body": [
        ("Eligibility and Office Attendance",
         "Hybrid working is a benefit that depends on role suitability and performance.",
         [Bullets(["Employees become eligible after completing probation of 6 months.",
                   "Employees must have a performance rating of 3 (Meets Expectations) or above in the latest cycle.",
                   "Hybrid employees work from the office 3 days per week, including the anchor days.",
                   "Office attendance is recorded through badge swipes and reviewed monthly by managers."])]),
        ("Availability and Right to Disconnect",
         "Flexibility must not reduce collaboration or customer responsiveness.",
         [Paragraph("All employees must be available online during core hours from 11:00 AM to 4:00 PM IST. Outside core "
                    "hours, employees may plan their work flexibly. Except for employees on an approved on-call roster, there "
                    "is no expectation to respond to messages between 8:00 PM and 8:00 AM.")]),
        ("Allowances",
         "Aranya supports a productive home workspace through the following allowances.",
         [Table(header=["Allowance", "Amount", "Frequency", "How it is paid"], col_widths=[0.28, 0.2, 0.24, 0.28],
                caption="Table 1: Hybrid work allowances", rows=[
                    ["WFH allowance (internet and utilities)", "Rs. 1,500", "Monthly", "Through payroll"],
                    ["Home office setup (chair, desk, lighting)", "Rs. 12,000", "Once every 3 years", "Reimbursed against invoice"],
                    ["Co-working space (approved cases)", "Rs. 6,000", "Monthly", "Reimbursed against invoice"],
                ])]),
        ("Work from Anywhere and Overseas Work",
         None,
         [Bullets(["Employees may work from another location in India for up to 30 working days per calendar year.",
                   "WFA requests must be raised in PeopleHub at least 10 working days in advance and approved by the manager.",
                   "Working from outside India is not permitted because of tax and permanent establishment risk, except with "
                   "Global Mobility approval for a maximum of 15 days.",
                   "Full remote working for medical reasons may be approved by the HRBP for up to 3 months at a time."])]),
    ],
    "procedure": [
        "Confirm hybrid eligibility with your manager and select your hybrid arrangement in PeopleHub.",
        "Use only company-issued laptops connected through the corporate VPN when working remotely.",
        "Never work on public Wi-Fi networks without the VPN switched on.",
        "Return all company equipment on the last working day in case of separation.",
    ],
    "exceptions": "Managers may require employees to attend office on additional days for business needs such as client "
                  "visits, audits or product launches, with at least 2 working days' notice.",
    "faqs": [
        ("Can I choose Monday and Friday as my office days?", "No. Hybrid employees must attend the office on the anchor days "
         "of Tuesday, Wednesday and Thursday."),
        ("Is the WFH allowance taxable?", "Yes. It is paid through payroll and taxed as per applicable income tax rules."),
        ("Can I work from my hometown during Diwali?", "Yes, under Work from Anywhere, within the 30-working-day annual limit "
         "and with manager approval."),
    ],
    "revisions": [("1.0", "1 April 2022", "Initial hybrid policy (2 office days per week)."),
                  ("2.0", "1 October 2025", "Moved to 3 office days with anchor days; WFA and right to disconnect added.")],
    "related": ["IT Acceptable Use and Information Security Policy (HR-POL-007)",
                "Attendance, Working Hours and Overtime Policy (HR-POL-009)"],
    "qa": [
        _qa("How many days per week must hybrid employees work from the office?", "3 days per week, including the anchor days "
            "(Tuesday, Wednesday and Thursday).", ["work from the office 3 days per week"]),
        _qa("What is the monthly WFH allowance?", "Rs. 1,500 per month, paid through payroll.",
            ["WFH allowance (internet and utilities)", "Rs. 1,500"], "table_lookup"),
        _qa("How many working days per year can an employee work from another location in India?", "Up to 30 working days "
            "per calendar year.", ["up to 30 working days per calendar year"]),
        _qa("What are the core hours under the hybrid policy?", "11:00 AM to 4:00 PM IST.",
            ["11:00 AM to 4:00 PM IST"]),
        _qa("How often can the home office setup amount be claimed and how much is it?", "Rs. 12,000 once every 3 years, "
            "reimbursed against invoice.", ["Rs. 12,000", "Once every 3 years"], "table_lookup", "medium"),
    ],
}

IT_SECURITY = {
    "policy_id": "HR-POL-007",
    "title": "IT Acceptable Use and Information Security Policy",
    "version": "4.2",
    "effective_date": "1 February 2026",
    "owner": "Chief Information Security Officer",
    "approver": "Chief Technology Officer",
    "review_cycle": "Annual",
    "purpose": "This policy defines the acceptable use of Aranya's information systems and the security practices every "
               "employee must follow to protect company, customer and employee information from loss, misuse and cyber attack.",
    "scope": "It applies to all employees, contractors and third parties who use Aranya laptops, mobile devices, networks, "
             "email, cloud services, software or data, whether in the office, at home or while travelling.",
    "definitions": [
        ("MFA", "Multi-factor authentication: a password plus a second factor such as an authenticator app."),
        ("SOC", "The Security Operations Centre, which monitors and responds to security incidents."),
        ("BYOD", "Bring Your Own Device: a personal phone or tablet used to access company email or apps."),
    ],
    "body": [
        ("Passwords and Access",
         "Strong authentication is the first line of defence against account compromise.",
         [Bullets(["Passwords must be at least 14 characters; long passphrases are encouraged.",
                   "The last 10 passwords cannot be reused. Passwords are changed only when compromise is suspected.",
                   "MFA is mandatory for email, VPN, Aranya PeopleHub and all cloud consoles.",
                   "Screens lock automatically after 5 minutes of inactivity; lock your screen whenever you leave your desk.",
                   "Never share credentials, including with IT support staff."])]),
        ("Data Classification",
         "All information must be labelled and handled according to its classification.",
         [Table(header=["Class", "Examples", "Handling rule"], col_widths=[0.16, 0.42, 0.42],
                caption="Table 1: Data classification and handling", rows=[
                    ["Public", "Marketing brochures, published blogs", "No restrictions"],
                    ["Internal", "Org charts, internal announcements", "Share only within Aranya"],
                    ["Confidential", "Customer contracts, source code, salary data", "Encrypt when sent outside Aranya; need-to-know access"],
                    ["Restricted", "Customer personal data, credentials, M&A plans", "Approved systems only; never on removable media or personal devices"],
                ])]),
        ("Devices, Software and Removable Media",
         None,
         [Bullets(["USB mass storage is blocked by default. Exceptions require an IT ticket approved by the CISO "
                   "and are valid for 30 days.",
                   "Install software only from the Aranya Software Center.",
                   "Company email on personal phones is allowed only through the Aranya Secure Workspace app; the company may "
                   "remotely wipe the work profile if the phone is lost or the employee leaves.",
                   "Only company-approved enterprise generative AI tools may be used for work. Confidential or Restricted "
                   "data must never be entered into public AI tools."])]),
        ("Incident Reporting",
         "Fast reporting limits the damage caused by security incidents.",
         [Paragraph("Report any suspected security incident, phishing email or malware to the SOC within 1 hour at "
                    "soc@aranya.example or on extension 7777. A lost or stolen laptop or phone must be reported within 2 hours, "
                    "and a copy of the police complaint must be submitted to IT within 48 hours.")]),
    ],
    "procedure": [
        "Complete the mandatory information security training within 30 days of joining and every year by 31 March.",
        "Participate in monthly phishing simulations; employees who fail twice in a quarter take a refresher module.",
        "Request access to systems through the IT service portal; access is reviewed by managers every quarter.",
        "Return all IT assets on or before the last working day.",
    ],
    "exceptions": "Security exceptions must be requested through the IT service portal, approved by the CISO and are valid for "
                  "a maximum of 90 days. Monitoring of company systems is carried out in line with applicable law.",
    "faqs": [
        ("Can I forward work email to my personal Gmail?", "No. Auto-forwarding to personal accounts is blocked and is a "
         "policy violation."),
        ("Can I use a public AI chatbot to summarise a customer contract?", "No. Customer contracts are Confidential and may "
         "only be processed in company-approved enterprise AI tools."),
        ("How long are emails retained?", "Business email is retained for 7 years and then deleted unless under legal hold."),
    ],
    "revisions": [("4.0", "1 April 2024", "Introduced BYOD through Secure Workspace."),
                  ("4.1", "1 January 2025", "Password minimum raised to 14 characters."),
                  ("4.2", "1 February 2026", "Added generative AI usage rules.")],
    "related": ["Data Privacy and Confidentiality Policy (HR-POL-008)", "Hybrid Work and Work From Home Policy (HR-POL-006)"],
    "qa": [
        _qa("What is the minimum password length?", "At least 14 characters.", ["at least 14 characters"]),
        _qa("Within how long must a suspected security incident be reported to the SOC?", "Within 1 hour.",
            ["to the SOC within 1 hour"], "procedural"),
        _qa("After how many minutes of inactivity do screens lock automatically?", "5 minutes.",
            ["after 5 minutes of inactivity"]),
        _qa("How long is a USB storage exception valid?", "30 days, after CISO approval of an IT ticket.",
            ["are valid for 30 days"], "factual", "medium"),
        _qa("How should Restricted data be handled?", "Only on approved systems; never on removable media or personal devices.",
            ["Approved systems only; never on removable media or personal devices"], "table_lookup", "medium"),
    ],
}

DATA_PRIVACY = {
    "policy_id": "HR-POL-008",
    "title": "Data Privacy and Confidentiality Policy",
    "version": "1.1",
    "effective_date": "1 December 2025",
    "owner": "Data Protection Officer",
    "approver": "Chief Executive Officer",
    "review_cycle": "Annual",
    "purpose": "This policy explains how Aranya collects, uses, stores and protects personal data of employees, candidates "
               "and customers in compliance with the Digital Personal Data Protection Act, 2023 (DPDP Act) and the DPDP Rules, "
               "and how employees must protect confidential business information.",
    "scope": "It applies to all personal data processed by Aranya in digital form, or collected in non-digital form and "
             "digitised later, and to every employee, contractor and vendor who handles such data.",
    "definitions": [
        ("Personal data", "Any data about an individual who is identifiable by or in relation to such data."),
        ("Data Fiduciary", "The entity that determines the purpose and means of processing; Aranya for employee data."),
        ("Data Principal", "The individual to whom the personal data relates."),
        ("Personal data breach", "Any unauthorised processing, accidental disclosure, loss of access or destruction of personal data."),
    ],
    "body": [
        ("Lawful Processing",
         "Aranya processes personal data only for lawful purposes, either with consent or for legitimate uses permitted by "
         "the DPDP Act, such as purposes of employment.",
         [Bullets(["Collect only the personal data needed for a stated purpose (data minimisation).",
                   "Give a clear notice describing the data collected and its purpose when consent is sought.",
                   "Use personal data only for the purpose for which it was collected.",
                   "Personal data may be transferred outside India only to countries not restricted by the Central Government."])]),
        ("Rights of Data Principals",
         "Employees and other data principals can exercise their rights by writing to the Data Protection Officer at "
         "dpo@aranya.example.",
         [Paragraph("Data principals have the right to access a summary of their personal data, to correct, complete or "
                    "update it, to erasure where it is no longer needed, to grievance redressal and to nominate another "
                    "person to exercise their rights. Aranya responds to every request within 30 days.")]),
        ("Retention",
         "Personal data is retained only as long as required for the purpose or by law.",
         [Table(header=["Record type", "Retention period"], col_widths=[0.55, 0.45],
                caption="Table 1: Retention schedule", rows=[
                    ["Employee personnel file", "8 years after separation"],
                    ["Candidate data (not hired)", "12 months, unless the candidate consents to longer retention"],
                    ["CCTV footage", "30 days"],
                    ["Background verification reports", "2 years after completion"],
                    ["Payroll and statutory records", "As required under applicable labour and tax law"],
                ])]),
        ("Personal Data Breach",
         "Speed matters when personal data may have been exposed.",
         [Paragraph("Any employee who suspects a personal data breach must report it to the DPO within 6 hours of discovery. "
                    "The DPO assesses the breach and, where required, intimates the Data Protection Board of India and affected "
                    "data principals without delay, followed by a detailed report to the Board within 72 hours as prescribed "
                    "under the DPDP Rules. Under the DPDP Act, failure to take reasonable security safeguards can attract a "
                    "penalty of up to Rs. 250 crore.")]),
        ("Confidential Information",
         None,
         [Paragraph("Employees must protect Aranya's confidential information, including source code, pricing, customer "
                    "lists and strategy documents, and follow the clean-desk practice. Confidentiality obligations continue "
                    "for 3 years after separation, and indefinitely for trade secrets.")]),
    ],
    "procedure": [
        "Complete the data privacy e-learning module within 30 days of joining.",
        "Before starting a new process that uses personal data, consult the DPO for a privacy review.",
        "Report suspected breaches to the DPO at dpo@aranya.example within 6 hours.",
        "Securely delete or anonymise personal data when the retention period ends.",
    ],
    "exceptions": "Any processing not covered by this policy, including new cross-border transfers, requires prior written "
                  "approval from the DPO.",
    "faqs": [
        ("Can I keep a copy of candidate CVs on my laptop?", "No. CVs must be stored only in the applicant tracking system "
         "and are deleted after 12 months unless the candidate consents."),
        ("Can my manager see my medical records?", "No. Medical information is accessible only to the HR benefits team and "
         "the insurer, on a need-to-know basis."),
        ("How do I correct my address in company records?", "Update it in PeopleHub or write to dpo@aranya.example."),
    ],
    "revisions": [("1.0", "1 April 2024", "Initial release aligned to the DPDP Act, 2023."),
                  ("1.1", "1 December 2025", "Updated breach timelines in line with the DPDP Rules.")],
    "related": ["IT Acceptable Use and Information Security Policy (HR-POL-007)", "Code of Conduct and Ethics (HR-POL-004)"],
    "qa": [
        _qa("Within how many hours must an employee report a suspected personal data breach to the DPO?",
            "Within 6 hours of discovery.", ["report it to the DPO within 6 hours of discovery"], "procedural"),
        _qa("How long is an employee's personnel file retained after separation?", "8 years after separation.",
            ["Employee personnel file", "8 years after separation"], "table_lookup"),
        _qa("How long is CCTV footage retained?", "30 days.", ["CCTV footage", "30 days"], "table_lookup"),
        _qa("What is the maximum penalty under the DPDP Act for failing to take reasonable security safeguards?",
            "Up to Rs. 250 crore.", ["penalty of up to Rs. 250 crore"], "factual", "medium"),
        _qa("How long do confidentiality obligations continue after an employee leaves?",
            "3 years after separation, and indefinitely for trade secrets.",
            ["continue for 3 years after separation"], "factual", "medium"),
    ],
}

ATTENDANCE = {
    "policy_id": "HR-POL-009",
    "title": "Attendance, Working Hours and Overtime Policy",
    "version": "2.3",
    "effective_date": "1 January 2026",
    "owner": "Head - Human Resources Operations",
    "approver": "Chief People Officer",
    "review_cycle": "Annual",
    "purpose": "This policy sets standard working hours, shift timings and attendance rules, and explains how overtime and "
               "night shift work are approved and compensated, in line with the Karnataka Shops and Commercial "
               "Establishments Act, 1961 and the Occupational Safety, Health and Working Conditions Code, 2020.",
    "scope": "It applies to all employees working from Aranya offices and client sites in India, including hybrid employees "
             "on their remote working days.",
    "definitions": [
        ("Working week", "Monday to Friday; Saturday and Sunday are weekly offs."),
        ("Late mark", "Recorded when the first punch is more than 15 minutes after the shift start time."),
        ("Overtime-eligible employee", "A non-managerial L1 employee in support or operations roles."),
    ],
    "body": [
        ("Working Hours and Shifts",
         "The standard working day is 9 hours including a 1-hour meal break, giving 40 working hours a week.",
         [Table(header=["Shift", "Timing", "Applicable to"], col_widths=[0.2, 0.35, 0.45], caption="Table 1: Shift timings", rows=[
             ["General", "9:30 AM to 6:30 PM", "All corporate and engineering roles"],
             ["Shift A", "6:00 AM to 3:00 PM", "Customer support (APAC)"],
             ["Shift B", "2:00 PM to 11:00 PM", "Customer support (EMEA)"],
             ["Shift C (night)", "10:00 PM to 7:00 AM", "Customer support (Americas) and infrastructure operations"],
         ])]),
        ("Attendance Recording",
         "Attendance is captured automatically through badge swipes in the office and through the PeopleHub mobile app on "
         "remote working days.",
         [Bullets(["A grace period of 15 minutes is allowed on the shift start time.",
                   "Up to 3 late marks per month are permitted. Each late mark beyond 3 results in a deduction of half a day "
                   "of Earned Leave.",
                   "Missing punches must be regularised in PeopleHub within 5 working days, with manager approval.",
                   "Absence without intimation for 8 consecutive working days is treated as abandonment of employment and a "
                   "show-cause notice is issued."])]),
        ("Overtime",
         "Overtime is work beyond 9 hours in a day or 48 hours in a week by an overtime-eligible employee.",
         [Paragraph("Overtime must be pre-approved by the manager in PeopleHub. It is paid at twice the ordinary rate of "
                    "wages and is capped at 50 hours per quarter per employee. Managers and employees in grade L2 and above "
                    "are not eligible for overtime pay; they receive compensatory off instead, as per the Leave Policy.")]),
        ("Night Shift",
         None,
         [Paragraph("Employees working Shift C receive a night shift allowance of Rs. 400 per night. Women employees work "
                    "night shifts only with their written consent. The company provides door-to-door cab transport with a "
                    "security guard for all night shift employees and ensures that women employees are not the first pickup "
                    "or last drop.")]),
    ],
    "procedure": [
        "Mark attendance by badge swipe in the office or by the PeopleHub app when working remotely.",
        "Request regularisation for any missing punch within 5 working days.",
        "Seek manager pre-approval for overtime before the extra hours are worked.",
        "Overtime and night shift allowances are paid with the next month's salary.",
    ],
    "exceptions": "Relaxation of attendance rules for medical or caregiving reasons may be approved by the HRBP for a defined "
                  "period, documented in PeopleHub.",
    "faqs": [
        ("I punched in at 9:50 AM for the general shift. Is that a late mark?", "Yes. The grace period ends at 9:45 AM, so a "
         "9:50 AM punch is recorded as a late mark."),
        ("Do I get overtime as an L3 Lead?", "No. Employees in grade L2 and above receive compensatory off instead of overtime pay."),
        ("Is the night shift allowance paid for Shift B?", "No. The allowance applies only to Shift C (10:00 PM to 7:00 AM)."),
    ],
    "revisions": [("2.2", "1 April 2024", "Added Shift C for Americas support."),
                  ("2.3", "1 January 2026", "Night shift allowance raised to Rs. 400; overtime cap clarified.")],
    "related": ["Leave Policy (HR-POL-001)", "Hybrid Work and Work From Home Policy (HR-POL-006)"],
    "qa": [
        _qa("What are the timings of the general shift?", "9:30 AM to 6:30 PM.", ["General", "9:30 AM to 6:30 PM"], "table_lookup"),
        _qa("How many late marks per month are permitted before leave is deducted?", "3 late marks; each additional late mark "
            "deducts half a day of Earned Leave.", ["Up to 3 late marks per month are permitted"]),
        _qa("At what rate is overtime paid and what is the cap?", "Twice the ordinary rate of wages, capped at 50 hours per quarter.",
            ["twice the ordinary rate of", "capped at 50 hours per quarter"], "factual", "medium"),
        _qa("What is the night shift allowance?", "Rs. 400 per night for Shift C.", ["night shift allowance of Rs. 400 per night"]),
        _qa("After how many days of unintimated absence is employment treated as abandoned?", "8 consecutive working days.",
            ["8 consecutive working days"], "factual", "medium"),
    ],
}

PERFORMANCE = {
    "policy_id": "HR-POL-010",
    "title": "Performance Management and Appraisal Policy",
    "version": "3.0",
    "effective_date": "1 April 2025",
    "owner": "Head - Talent Management",
    "approver": "Chief People Officer",
    "review_cycle": "Annual",
    "purpose": "This policy describes how performance is planned, reviewed, rated and rewarded at Aranya. It aims to make "
               "expectations clear, encourage continuous feedback and link pay and promotions fairly to performance.",
    "scope": "It applies to all confirmed employees in grades L1 to L6. Performance of L7 executives is reviewed by the "
             "Nomination and Remuneration Committee.",
    "definitions": [
        ("Performance cycle", "The financial year from 1 April to 31 March."),
        ("Calibration", "A review meeting where managers compare ratings across teams for consistency."),
        ("PIP", "Performance Improvement Plan, a structured plan to address performance gaps."),
    ],
    "body": [
        ("Annual Calendar",
         "The performance cycle follows the financial year with fixed milestones.",
         [Table(header=["Milestone", "Timeline"], col_widths=[0.55, 0.45], caption="Table 1: Performance calendar", rows=[
             ["Goal setting (4 to 7 goals, weights totalling 100%)", "By 30 April"],
             ["Mid-year check-in", "1 to 31 October"],
             ["Self-assessment", "1 to 15 April (following year)"],
             ["Manager assessment", "16 to 30 April"],
             ["Calibration", "May"],
             ["Ratings communicated", "By 31 May"],
             ["Increments effective", "1 July"],
         ])]),
        ("Rating Scale and Rewards",
         "Each employee receives one overall rating on a 5-point scale. Increment and bonus guidelines are indicative and "
         "depend on budget and market position.",
         [Table(header=["Rating", "Label", "Increment guideline", "Bonus multiplier"], col_widths=[0.12, 0.33, 0.28, 0.27],
                caption="Table 2: Rating scale, increment and bonus guidelines", rows=[
                    ["5", "Outstanding", "12% to 15%", "150%"],
                    ["4", "Exceeds Expectations", "8% to 11%", "120%"],
                    ["3", "Meets Expectations", "5% to 7%", "100%"],
                    ["2", "Partially Meets Expectations", "0% to 3%", "50%"],
                    ["1", "Does Not Meet Expectations", "0% (PIP initiated)", "0%"],
                ])]),
        ("Eligibility and Promotions",
         None,
         [Bullets(["Employees who join on or before 31 December are rated in that cycle; those who join later are rated in "
                   "the next cycle.",
                   "Promotion eligibility requires at least 18 months in the current grade and a rating of 4 or 5 in the "
                   "latest cycle, with a rating of at least 3 in the previous cycle.",
                   "Employees on a PIP or with an active final written warning are not eligible for promotion."])]),
        ("Performance Improvement Plan",
         None,
         [Paragraph("A PIP lasts 60 days, with documented reviews every two weeks between the employee, manager and HRBP. "
                    "Successful completion closes the PIP; unsuccessful completion may lead to role change or separation in "
                    "line with the Code of Conduct and Ethics.")]),
    ],
    "procedure": [
        "Set goals in PeopleHub by 30 April and align them with your manager.",
        "Hold regular one-to-one conversations and complete the mid-year check-in in October.",
        "Submit the self-assessment between 1 and 15 April at the end of the cycle.",
        "Appeal a rating within 10 working days of communication to the skip-level manager and HRBP; appeals are resolved "
        "within 15 working days.",
    ],
    "exceptions": "Ratings are final after 30 June and are not changed after that date. Employees on long leave of more than "
                  "6 months in the cycle receive a 'Not Rated' status.",
    "faqs": [
        ("I joined on 15 January. Will I be rated this cycle?", "No. Employees who join after 31 December are rated in the next cycle."),
        ("Is forced distribution used?", "No. Calibration ensures consistency, but there is no forced distribution curve."),
        ("Can I appeal my rating after a month?", "No. Appeals must be raised within 10 working days of the rating being communicated."),
    ],
    "revisions": [("2.0", "1 April 2022", "Introduced calibration."),
                  ("3.0", "1 April 2025", "Removed forced distribution; added bonus multipliers.")],
    "related": ["Code of Conduct and Ethics (HR-POL-004)", "Whistleblower and Grievance Redressal Policy (HR-POL-011)"],
    "qa": [
        _qa("What increment range applies to a rating of 4?", "8% to 11%.", ["Exceeds Expectations", "8% to 11%"], "table_lookup"),
        _qa("What is the bonus multiplier for an Outstanding rating?", "150%.", ["Outstanding", "150%"], "table_lookup"),
        _qa("How long is a Performance Improvement Plan?", "60 days, with reviews every two weeks.", ["A PIP lasts 60 days"]),
        _qa("What is required to be eligible for promotion?", "At least 18 months in the current grade and a rating of 4 or 5 in "
            "the latest cycle, with at least 3 in the previous cycle.", ["at least 18 months in the current grade"], "factual", "medium"),
        _qa("When do annual increments take effect?", "1 July.", ["Increments effective", "1 July"], "table_lookup"),
    ],
}

WHISTLEBLOWER = {
    "policy_id": "HR-POL-011",
    "title": "Whistleblower and Grievance Redressal Policy",
    "version": "2.0",
    "effective_date": "1 August 2025",
    "owner": "Chief Ethics and Compliance Officer",
    "approver": "Audit Committee of the Board",
    "review_cycle": "Every 2 years",
    "purpose": "This policy provides safe channels for employees and stakeholders to report unethical behaviour, fraud or "
               "violations of law without fear of retaliation, and a fair process to resolve workplace grievances. It "
               "serves as the vigil mechanism under Section 177 of the Companies Act, 2013.",
    "scope": "It applies to all employees, directors, vendors, customers and other stakeholders of Aranya. Workplace "
             "grievances covered by Part B apply to employees only.",
    "definitions": [
        ("Protected disclosure", "A report made in good faith about actual or suspected wrongdoing."),
        ("Ombudsperson", "The senior independent officer appointed by the Audit Committee to oversee investigations."),
        ("Retaliation", "Any adverse action taken against a person because they made a protected disclosure."),
    ],
    "body": [
        ("Part A: Reporting Channels",
         "Concerns can be raised through any of the following channels, all of which accept anonymous reports.",
         [Bullets(["Ethics hotline 1800-000-3344, available 24 x 7 and operated by the independent provider ClearVoice Ethics Services.",
                   "Web portal at ethics.aranya.example.",
                   "Email to ethics@aranya.example.",
                   "Letter marked 'Strictly Confidential' to the Ombudsperson at the registered office.",
                   "Complaints against the CEO or a director may be sent directly to the Chair of the Audit Committee."])]),
        ("Part A: Investigation Timelines",
         "Every disclosure is handled confidentially by the Ombudsperson.",
         [Table(header=["Step", "Timeline"], col_widths=[0.6, 0.4], caption="Table 1: Whistleblower investigation timelines", rows=[
             ["Acknowledgement of disclosure", "Within 3 working days"],
             ["Preliminary assessment", "Within 10 working days"],
             ["Completion of investigation", "Within 45 days"],
             ["Extension (with Audit Committee approval)", "Up to 30 additional days"],
             ["Retention of investigation records", "8 years"],
         ]),
          Paragraph("Retaliation against a whistleblower is treated as gross misconduct. Disclosures found to be knowingly "
                    "false or malicious may lead to disciplinary action against the person making them.")]),
        ("Part B: Grievance Redressal",
         "Employees may raise grievances about working conditions, pay, policies or treatment through a three-level process.",
         [Table(header=["Level", "Handled by", "Resolution time"], col_widths=[0.15, 0.55, 0.3],
                caption="Table 2: Grievance escalation levels", rows=[
                    ["Level 1", "Reporting manager", "5 working days"],
                    ["Level 2", "HR Business Partner", "10 working days"],
                    ["Level 3", "Grievance Redressal Committee", "15 working days"],
                ]),
          Paragraph("The Grievance Redressal Committee is constituted under the Industrial Relations Code, 2020 with equal "
                    "representation of employer and employee members, and not more than 10 members in total. Complaints of "
                    "sexual harassment are handled only by the Internal Committee under the POSH Policy (HR-POL-005), and "
                    "rating disputes follow the appeal process in the Performance Management Policy (HR-POL-010).")]),
    ],
    "procedure": [
        "Raise a disclosure through any channel with as much factual detail as possible.",
        "Note the reference number provided by the hotline or portal to track anonymous reports.",
        "Cooperate with the investigation and maintain confidentiality.",
        "For grievances, start at Level 1 unless the grievance concerns the reporting manager, in which case go directly to Level 2.",
    ],
    "exceptions": "The Audit Committee may vary investigation timelines in complex cases. No exceptions are permitted to the "
                  "protection against retaliation.",
    "faqs": [
        ("Will my identity be revealed to the person I report?", "No. Identity is protected and shared only with the "
         "investigation team where essential."),
        ("Can a vendor use the ethics hotline?", "Yes. Part A is open to vendors, customers and other stakeholders."),
        ("My grievance is about my manager. Where do I start?", "Go directly to Level 2, the HR Business Partner."),
    ],
    "revisions": [("1.0", "1 August 2021", "Initial vigil mechanism."),
                  ("2.0", "1 August 2025", "Added third-party hotline and grievance levels.")],
    "related": ["Code of Conduct and Ethics (HR-POL-004)", "Prevention of Sexual Harassment (POSH) Policy (HR-POL-005)"],
    "qa": [
        _qa("What is the ethics hotline number?", "1800-000-3344, available 24 x 7.", ["Ethics hotline 1800-000-3344"]),
        _qa("Within how many days must a whistleblower investigation be completed?", "Within 45 days, extendable by up to 30 "
            "days with Audit Committee approval.", ["Completion of investigation", "Within 45 days"], "table_lookup"),
        _qa("How long does a Level 2 grievance take to resolve and who handles it?", "10 working days, handled by the HR "
            "Business Partner.", ["Level 2", "HR Business Partner", "10 working days"], "table_lookup", "medium"),
        _qa("Who can receive complaints against the CEO?", "The Chair of the Audit Committee.",
            ["directly to the Chair of the Audit Committee"], "factual", "medium"),
        _qa("Within how many working days is a whistleblower disclosure acknowledged?", "Within 3 working days.",
            ["Acknowledgement of disclosure", "Within 3 working days"], "table_lookup"),
    ],
}

ANTI_BRIBERY = {
    "policy_id": "HR-POL-012",
    "title": "Anti-Bribery and Anti-Corruption Policy",
    "version": "2.1",
    "effective_date": "1 March 2025",
    "owner": "General Counsel",
    "approver": "Board of Directors",
    "review_cycle": "Annual",
    "purpose": "Aranya has zero tolerance for bribery and corruption in any form. This policy sets out the rules employees "
               "and third parties must follow to comply with the Prevention of Corruption Act, 1988 (as amended in 2018) "
               "and, for overseas business, laws such as the US Foreign Corrupt Practices Act and the UK Bribery Act.",
    "scope": "It applies to all employees and directors, and to agents, consultants, distributors and vendors acting on "
             "behalf of Aranya anywhere in the world.",
    "definitions": [
        ("Bribe", "Anything of value offered, given or received to improperly influence a decision."),
        ("Facilitation payment", "A small unofficial payment to speed up a routine government action."),
        ("Government official", "Any employee of a government, public sector undertaking or public international organisation."),
    ],
    "body": [
        ("Prohibited Conduct",
         "Employees must never offer, promise, give, request or accept a bribe, directly or through a third party.",
         [Bullets(["Facilitation payments are prohibited, even where they are customary or small in amount.",
                   "Aranya makes no contributions to political parties or candidates.",
                   "Employees must not use personal funds to do what this policy prohibits the company from doing.",
                   "Under Section 9 of the amended Act, the company itself can be liable if an associated person bribes on its behalf."])]),
        ("Gifts and Hospitality Limits",
         "Gifts and hospitality offered to business partners must be reasonable, transparent and never linked to a decision.",
         [Table(header=["Item", "Limit"], col_widths=[0.55, 0.45], caption="Table 1: Limits on gifts and hospitality given", rows=[
             ["Gift to a business partner (per occasion)", "Rs. 3,000 per person"],
             ["Gifts to a business partner (per year)", "Rs. 6,000 per person"],
             ["Hospitality (meals, events)", "Rs. 5,000 per person per event"],
             ["Gift to a government official", "Only logo items up to Rs. 500"],
             ["Register entry required", "Any gift or hospitality above Rs. 1,000, within 7 days"],
         ])]),
        ("Donations, Sponsorships and Third Parties",
         None,
         [Paragraph("All charitable donations and sponsorships require a review by the Legal team, and any donation above "
                    "Rs. 1,00,000 also requires approval from the Chief Financial Officer. Before onboarding agents, "
                    "distributors or vendors in high-risk categories, risk-based due diligence must be completed and an "
                    "anti-bribery clause included in the contract. Red flags include requests for cash, unusual commissions, "
                    "and payments to offshore accounts.")]),
    ],
    "procedure": [
        "Record every gift or hospitality above Rs. 1,000 in the Gift and Hospitality Register within 7 days.",
        "Complete the anti-bribery training and annual compliance certification by 31 March each year.",
        "Report any bribe request or suspicion through the Whistleblower and Grievance Redressal Policy (HR-POL-011).",
        "Maintain accurate books and records for all payments; off-book accounts are prohibited.",
    ],
    "exceptions": "Where an employee faces an immediate threat to personal safety, a payment demanded under duress may be made "
                  "and must be reported to the General Counsel within 24 hours. No other exceptions are permitted.",
    "faqs": [
        ("A customs officer asks for Rs. 500 to clear a shipment faster. Can I pay?", "No. This is a facilitation payment "
         "and is prohibited. Report it to Legal."),
        ("Can I take a client to dinner costing Rs. 4,000 per person?", "Yes. It is within the Rs. 5,000 hospitality limit, "
         "but it must be recorded in the register because it exceeds Rs. 1,000."),
        ("Can we sponsor a client's industry conference?", "Only after Legal review, and CFO approval if the amount exceeds Rs. 1,00,000."),
    ],
    "revisions": [("2.0", "1 March 2023", "Added third-party due diligence."),
                  ("2.1", "1 March 2025", "Revised gift and hospitality limits.")],
    "related": ["Code of Conduct and Ethics (HR-POL-004)", "Travel and Expense Claims Policy (HR-POL-002)"],
    "qa": [
        _qa("What is the per-occasion limit for a gift to a business partner?", "Rs. 3,000 per person.",
            ["Gift to a business partner (per occasion)", "Rs. 3,000 per person"], "table_lookup"),
        _qa("What is the hospitality limit per person per event?", "Rs. 5,000 per person per event.",
            ["Rs. 5,000 per person per event"], "table_lookup"),
        _qa("Are facilitation payments allowed?", "No. Facilitation payments are prohibited, even if customary or small.",
            ["Facilitation payments are prohibited"]),
        _qa("Above what amount does a donation need CFO approval?", "Above Rs. 1,00,000.",
            ["any donation above", "Rs. 1,00,000"], "factual", "medium"),
        _qa("What may be given to a government official?", "Only logo items up to Rs. 500.",
            ["Only logo items up to Rs. 500"], "table_lookup", "medium"),
    ],
}

SEPARATION = {
    "policy_id": "HR-POL-013",
    "title": "Separation, Notice Period and Full and Final Settlement Policy",
    "version": "2.2",
    "effective_date": "21 November 2025",
    "owner": "Head - Human Resources Operations",
    "approver": "Chief People Officer",
    "review_cycle": "Annual",
    "purpose": "This policy explains how employment with Aranya ends, the notice periods that apply, the exit process and "
               "how the full and final (F&F) settlement, including gratuity, is calculated and paid in line with the Code on "
               "Wages, 2019 and the Code on Social Security, 2020.",
    "scope": "It applies to all employees of Aranya Technologies in India for resignation, termination, retirement and the "
             "end of fixed-term contracts.",
    "definitions": [
        ("Last working day (LWD)", "The final day of employment after serving or buying out the notice period."),
        ("Notice buyout", "Payment in lieu of the unserved portion of the notice period."),
        ("F&F settlement", "The final calculation of all dues payable to or recoverable from the employee."),
    ],
    "body": [
        ("Notice Periods",
         "Notice periods apply equally to resignation by the employee and termination by the company (other than for misconduct).",
         [Table(header=["Employee category", "Notice period"], col_widths=[0.6, 0.4], caption="Table 1: Notice periods", rows=[
             ["Employees on probation", "15 days"],
             ["Confirmed employees, L1 to L3", "60 days"],
             ["Confirmed employees, L4 to L5", "90 days"],
             ["Confirmed employees, L6 and above", "90 days"],
         ]),
          Paragraph("A shortfall in notice may be bought out by paying basic salary for the unserved days, with approval from "
                    "the manager and HRBP. Earned Leave cannot be adjusted against the notice period unless approved by the "
                    "HRBP. A resignation may be withdrawn within 7 days of submission with manager approval.")]),
        ("Exit Process",
         "The exit process ensures a smooth handover and protects company assets and information.",
         [Bullets(["Resignation is submitted in PeopleHub under Separation > Resign.",
                   "Knowledge transfer is planned with the manager during the notice period.",
                   "All IT assets, ID cards and access cards are returned on or before the last working day.",
                   "Outstanding advances and dues are settled with Finance before clearance.",
                   "An exit interview is conducted by the HRBP in the final week."])]),
        ("Full and Final Settlement",
         "The F&F settlement includes final salary, leave encashment, bonus, reimbursements and gratuity, less recoveries.",
         [Bullets(["Final wages are paid within 2 working days of the last working day, as required under the Code on Wages, 2019.",
                   "Other F&F components, such as leave encashment, pending reimbursements and variable pay, are paid within 30 days.",
                   "Earned Leave encashment is limited to 30 days, as per Leave Policy v3.0.",
                   "The relieving letter and experience letter are issued within 7 working days of F&F completion."])]),
        ("Gratuity",
         None,
         [Paragraph("Gratuity is payable to employees who complete 5 years of continuous service, and to fixed-term employees "
                    "after 1 year of service under the Code on Social Security, 2020. Gratuity is calculated as 15 x last "
                    "drawn monthly basic salary (including dearness allowance) x completed years of service / 26, subject to "
                    "the statutory ceiling of Rs. 20,00,000. It is paid within 30 days of becoming payable. The retirement age "
                    "at Aranya is 60 years.")]),
    ],
    "procedure": [
        "Submit the resignation in PeopleHub; the manager acknowledges it within 2 working days.",
        "Agree the last working day with the manager and HRBP, including any notice buyout.",
        "Complete the clearance checklist with IT, Finance, Admin and the manager.",
        "Transfer the Provident Fund balance using your UAN on the EPFO portal after exit.",
    ],
    "exceptions": "Employees terminated for proven misconduct are not entitled to notice or notice pay. The Chief People "
                  "Officer may waive part of the notice period in exceptional circumstances.",
    "faqs": [
        ("I am an L4 Manager. How long is my notice period?", "90 days."),
        ("Can I use my leave balance to shorten my notice period?", "Only with HRBP approval; otherwise leave is encashed "
         "up to 30 days in the F&F settlement."),
        ("When will I receive my final salary?", "Within 2 working days of your last working day; other components follow "
         "within 30 days."),
    ],
    "revisions": [("2.1", "1 April 2024", "Introduced resignation withdrawal window."),
                  ("2.2", "21 November 2025", "Aligned F&F timelines and fixed-term gratuity with the new Labour Codes.")],
    "related": ["Leave Policy (HR-POL-001)", "Code of Conduct and Ethics (HR-POL-004)"],
    "qa": [
        _qa("What is the notice period for a confirmed L2 employee?", "60 days.",
            ["Confirmed employees, L1 to L3", "60 days"], "table_lookup"),
        _qa("Within how many days of the last working day are final wages paid?", "Within 2 working days, as required under "
            "the Code on Wages, 2019.", ["Final wages are paid within 2 working days of the last working day"]),
        _qa("How is gratuity calculated and what is the ceiling?", "15 x last drawn monthly basic (including DA) x completed "
            "years of service / 26, subject to a ceiling of Rs. 20,00,000.", ["statutory ceiling of Rs. 20,00,000"], "factual", "medium"),
        _qa("After how much service is a fixed-term employee eligible for gratuity?", "After 1 year of service.",
            ["fixed-term employees", "after 1 year of service"], "factual", "medium"),
        _qa("What is the maximum earned leave that can be encashed at separation?",
            "30 days (as per Leave Policy v3.0; the superseded v2.0 allowed 20 days).",
            ["Earned Leave encashment is limited to 30 days"], "version_conflict", "hard"),
        _qa("What is the retirement age at Aranya?", "60 years.", ["retirement age", "60 years"]),
    ],
}


POLICIES: list[dict] = [
    _leave_policy(LEAVE_V3, current=True),
    _leave_policy(LEAVE_V2, current=False),
    _travel_policy(TRAVEL_V4, current=True),
    _travel_policy(TRAVEL_V3, current=False),
    MEDICAL,
    CODE_OF_CONDUCT,
    POSH,
    HYBRID,
    IT_SECURITY,
    DATA_PRIVACY,
    ATTENDANCE,
    PERFORMANCE,
    WHISTLEBLOWER,
    ANTI_BRIBERY,
    SEPARATION,
]
