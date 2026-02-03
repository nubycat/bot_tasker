def normalize_time_hhmm(value: str) -> str:
    s = value.strip()

    if ":" in s:
        parts = s.split(":")
        if len(parts) != 2:
            raise ValueError("bad format")

        h_str, m_str = parts[0], parts[1]
        if not (h_str.isdigit() and m_str.isdigit()):
            raise ValueError("not digits")

        h = int(h_str)
        m = int(m_str)
    else:
        if not s.isdigit():
            raise ValueError("not digits")
        h = int(s)
        m = 0

    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError("out of range")

    return f"{h:02d}:{m:02d}"
