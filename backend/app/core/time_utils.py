import re


def normalize_time_hhmm(value: str) -> str:
    s = value.strip()

    hh: int
    mm: int

    # 18 -> 18:00
    if re.fullmatch(r"\d{1,2}", s):
        hh = int(s)
        mm = 0

    # 830 -> 08:30, 2118 -> 21:18
    elif re.fullmatch(r"\d{3,4}", s):
        if len(s) == 3:
            hh = int(s[0])
            mm = int(s[1:])
        else:
            hh = int(s[:2])
            mm = int(s[2:])

    # 8:3 -> 08:03, 18:30 -> 18:30
    elif re.fullmatch(r"\d{1,2}:\d{1,2}", s):
        hh_s, mm_s = s.split(":", 1)
        hh = int(hh_s)
        mm = int(mm_s)

    else:
        raise ValueError("Invalid time format. Use 18, 18:30, 830, 2118")

    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError("Invalid time value")

    return f"{hh:02d}:{mm:02d}"
