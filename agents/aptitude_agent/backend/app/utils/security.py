import re


def clean_text(value, maximum=3000):
    value = re.sub(r"<[^>]+>", "", str(value or ""))
    return re.sub(r"\s+", " ", value).strip()[:maximum]


def client_ip(request):
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.remote_addr) or "unknown"

