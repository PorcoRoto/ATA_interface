def analyze_work_burden(
    salary,
    salary_type="annual",          # "annual" or "hourly"
    hours_per_week=40,
    weeks_per_year=52,
    monthly_rent=0.0,
    dependents=0,
    filing_status="single",        # "single" or "mfj" (married filing jointly)
    state_tax_rate=None,           # optional override; otherwise uses NM estimate
    print_output=True
):
    """
    Calculate monthly tax burden, rent, and remainder in terms of hours worked.

    Parameters
    ----------
    salary : float
        Either annual gross salary or hourly wage, depending on salary_type.
    salary_type : str
        "annual" or "hourly".
    hours_per_week : float
        Used only if salary_type == "hourly" to annualize.
    weeks_per_year : float
        Typically 52; use 50 if you want to account for unpaid time off.
    monthly_rent : float
        Monthly rent or mortgage interest payment.
    dependents : int
        Number of qualifying children for the Child Tax Credit.
    filing_status : str
        "single" or "mfj".
    state_tax_rate : float or None
        If provided, overrides the New Mexico estimate (as a decimal, e.g., 0.03).
    print_output : bool
        Whether to print a formatted summary.

    Returns
    -------
    dict with keys:
        hourly_wage, annual_gross, monthly_gross,
        monthly_federal_tax, monthly_fica, monthly_state_tax,
        monthly_tax_total, monthly_rent, monthly_remainder,
        hours_for_taxes, hours_for_rent, hours_for_remainder,
        shifts_for_taxes, shifts_for_rent, shifts_for_remainder
        (shifts assume 12-hour shifts; adjust SHIFT_HOURS below)
    """

    SHIFT_HOURS = 12  # set to 8 if you want 8-hour days

    # --- 1. Normalize to hourly wage and annual gross ---
    if salary_type == "annual":
        annual_gross = float(salary)
        total_hours = hours_per_week * weeks_per_year
        hourly_wage = annual_gross / total_hours if total_hours else 0
    elif salary_type == "hourly":
        hourly_wage = float(salary)
        annual_gross = hourly_wage * hours_per_week * weeks_per_year
    else:
        raise ValueError("salary_type must be 'annual' or 'hourly'")

    monthly_gross = annual_gross / 12.0
    monthly_hours = (hours_per_week * weeks_per_year) / 12.0

    # --- 2. FICA (Social Security + Medicare) ---
    # 2026 rates: 6.2% SS up to wage base, 1.45% Medicare (no cap for our range)
    SS_WAGE_BASE = 184500  # approximate 2026 base
    ss_taxable = min(annual_gross, SS_WAGE_BASE)
    fica_annual = ss_taxable * 0.062 + annual_gross * 0.0145

    # --- 3. Federal income tax (2026 brackets) ---
    if filing_status == "single":
        standard_deduction = 16100
        brackets = [
            (12400, 0.10),
            (50400, 0.12),
            (105700, 0.22),
            (201775, 0.24),
            (256500, 0.32),
            (640600, 0.35),
            (float("inf"), 0.37),
        ]
    elif filing_status == "mfj":
        standard_deduction = 32200
        brackets = [
            (24800, 0.10),
            (100800, 0.12),
            (211400, 0.22),
            (403550, 0.24),
            (513000, 0.32),
            (768700, 0.35),
            (float("inf"), 0.37),
        ]
    else:
        raise ValueError("filing_status must be 'single' or 'mfj'")

    taxable_income = max(0.0, annual_gross - standard_deduction)
    federal_tax = 0.0
    prev_limit = 0.0
    for limit, rate in brackets:
        if taxable_income > prev_limit:
            federal_tax += (min(taxable_income, limit) - prev_limit) * rate
            prev_limit = limit
        else:
            break

    # Child Tax Credit (2026: $2,200 per qualifying child, phase-out above $200k single / $400k MFJ)
    ctc = 0.0
    if dependents > 0:
        phase_out_threshold = 200000 if filing_status == "single" else 400000
        excess = max(0.0, annual_gross - phase_out_threshold)
        reduction = (excess // 1000) * 50  # $50 per $1,000 over threshold
        ctc = max(0.0, dependents * 2200 - reduction)
    federal_tax_net = max(0.0, federal_tax - ctc)

    # --- 4. State income tax (New Mexico estimate) ---
    if state_tax_rate is None:
        # Rough NM effective rate for single filer; adjust as needed
        if filing_status == "single":
            state_tax_annual = max(0.0, (annual_gross - 19000)) * 0.043
        else:
            state_tax_annual = max(0.0, (annual_gross - 38000)) * 0.043
    else:
        state_tax_annual = annual_gross * state_tax_rate

    # --- 5. Monthly totals ---
    monthly_fica = fica_annual / 12.0
    monthly_federal = federal_tax_net / 12.0
    monthly_state = state_tax_annual / 12.0
    monthly_tax_total = monthly_fica + monthly_federal + monthly_state

    monthly_remainder = monthly_gross - monthly_tax_total - monthly_rent

    # --- 6. Convert to hours and shifts ---
    def hours(cost):
        return cost / hourly_wage if hourly_wage else float("inf")

    hours_taxes = hours(monthly_tax_total)
    hours_rent = hours(monthly_rent)
    hours_remainder = hours(monthly_remainder)

    result = {
        "hourly_wage": round(hourly_wage, 2),
        "annual_gross": round(annual_gross, 2),
        "monthly_gross": round(monthly_gross, 2),
        "monthly_fica": round(monthly_fica, 2),
        "monthly_federal_tax": round(monthly_federal, 2),
        "monthly_state_tax": round(monthly_state, 2),
        "monthly_tax_total": round(monthly_tax_total, 2),
        "monthly_rent": round(monthly_rent, 2),
        "monthly_remainder": round(monthly_remainder, 2),
        "monthly_hours_worked": round(monthly_hours, 1),
        "hours_for_taxes": round(hours_taxes, 1),
        "hours_for_rent": round(hours_rent, 1),
        "hours_for_remainder": round(hours_remainder, 1),
        "shifts_for_taxes": round(hours_taxes / SHIFT_HOURS, 2),
        "shifts_for_rent": round(hours_rent / SHIFT_HOURS, 2),
        "shifts_for_remainder": round(hours_remainder / SHIFT_HOURS, 2),
        "shift_hours": SHIFT_HOURS,
    }

    if print_output:
        print("=" * 55)
        print(f"  WORK-BURDEN ANALYSIS  ({filing_status.upper()}, {dependents} dependent(s))")
        print("=" * 55)
        print(f"  Hourly wage:            ${result['hourly_wage']:>10,.2f}")
        print(f"  Annual gross:           ${result['annual_gross']:>10,.2f}")
        print(f"  Monthly gross:          ${result['monthly_gross']:>10,.2f}")
        print(f"  Monthly hours worked:   {result['monthly_hours_worked']:>10,.1f} hrs")
        print("-" * 55)
        print(f"  FICA:                   ${result['monthly_fica']:>10,.2f}")
        print(f"  Federal income tax:     ${result['monthly_federal_tax']:>10,.2f}")
        print(f"  State income tax:       ${result['monthly_state_tax']:>10,.2f}")
        print(f"  TOTAL TAXES:            ${result['monthly_tax_total']:>10,.2f}")
        print(f"  RENT:                   ${result['monthly_rent']:>10,.2f}")
        print(f"  REMAINDER:              ${result['monthly_remainder']:>10,.2f}")
        print("-" * 55)
        print(f"  Hours for taxes:        {result['hours_for_taxes']:>10,.1f} hrs "
              f"({result['shifts_for_taxes']:.2f} shifts)")
        print(f"  Hours for rent:         {result['hours_for_rent']:>10,.1f} hrs "
              f"({result['shifts_for_rent']:.2f} shifts)")
        print(f"  Hours for remainder:    {result['hours_for_remainder']:>10,.1f} hrs "
              f"({result['shifts_for_remainder']:.2f} shifts)")
        print("=" * 55)

    return result


# --- Example: 2026 paramedic in Albuquerque ---
if __name__ == "__main__":
    analyze_work_burden(
        salary=26,
        salary_type="hourly",
        hours_per_week=40,
        monthly_rent=1700,
        dependents=1,
        filing_status="single",
    )

    print()

    # --- Example: 1995 plumber, homeowner (interest-only as "rent") ---
    analyze_work_burden(
        salary=18,
        salary_type="hourly",
        hours_per_week=40,
        monthly_rent=755,   # first-month mortgage interest
        dependents=1,
        filing_status="mfj",
        state_tax_rate=0.027,  # rough NM effective rate
    )
    
def prompt_work_burden():
    """
    Interactively prompt the user for inputs and run analyze_work_burden.
    Returns the result dict from analyze_work_burden.
    """

    def ask(prompt, default=None, cast=str):
        """Prompt with optional default, keep asking on invalid input."""
        suffix = f" [{default}]" if default is not None else ""
        while True:
            raw = input(f"{prompt}{suffix}: ").strip()
            if raw == "" and default is not None:
                return default
            try:
                return cast(raw)
            except (ValueError, TypeError):
                print(f"  ⚠ Invalid input. Please enter a valid {cast.__name__}.")

    def ask_choice(prompt, choices, default=None):
        """Prompt until user enters one of the allowed choices."""
        choices_str = "/".join(choices)
        suffix = f" [{default}]" if default is not None else ""
        while True:
            raw = input(f"{prompt} ({choices_str}){suffix}: ").strip().lower()
            if raw == "" and default is not None:
                return default
            if raw in choices:
                return raw
            print(f"  ⚠ Please choose one of: {choices_str}")

    print("\n" + "=" * 55)
    print("  WORK-BURDEN ANALYSIS — INPUT WIZARD")
    print("=" * 55)

    # --- Salary ---
    salary_type = ask_choice(
        "Is the salary annual or hourly?",
        ["annual", "hourly"],
        default="hourly",
    )
    salary = ask(
        f"Enter the {salary_type} salary"
        + (" (e.g., 26.00 for $26/hr)" if salary_type == "hourly" else " (e.g., 54080)"),
        cast=float,
    )

    # --- Hours (only meaningful for hourly; still ask for context) ---
    hours_per_week = ask(
        "Hours worked per week",
        default=40.0,
        cast=float,
    )
    weeks_per_year = ask(
        "Weeks worked per year (use 52 for full year)",
        default=52.0,
        cast=float,
    )

    # --- Rent ---
    monthly_rent = ask(
        "Monthly rent (or mortgage interest if a homeowner)",
        default=0.0,
        cast=float,
    )

    # --- Dependents ---
    dependents = ask(
        "Number of qualifying dependent children",
        default=0,
        cast=int,
    )

    # --- Filing status ---
    filing_status = ask_choice(
        "Filing status",
        ["single", "mfj"],
        default="single",
    )

    # --- Optional state tax override ---
    override = ask_choice(
        "Override the default New Mexico state tax estimate?",
        ["yes", "no"],
        default="no",
    )
    state_tax_rate = None
    if override == "yes":
        state_tax_rate = ask(
            "Enter effective state tax rate as a decimal (e.g., 0.03 for 3%)",
            cast=float,
        )

    print("\nRunning analysis...\n")

    result = analyze_work_burden(
        salary=salary,
        salary_type=salary_type,
        hours_per_week=hours_per_week,
        weeks_per_year=weeks_per_year,
        monthly_rent=monthly_rent,
        dependents=dependents,
        filing_status=filing_status,
        state_tax_rate=state_tax_rate,
        print_output=True,
    )

    return result


if __name__ == "__main__":
    prompt_work_burden()