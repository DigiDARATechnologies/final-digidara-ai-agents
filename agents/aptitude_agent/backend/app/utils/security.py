import re

# Only real HTML tags. The old "<[^>]+>" also ate maths: in "B < C, C > D" it
# took "< C, C >" for a tag and left the learner with "B D". A tag must start
# right after "<", attributes must have "=", and it can't touch the word before
# it, so "x<y and y>z", "A<B>C" and "List<String>" all survive.
_HTML_TAG = re.compile(
    r"(?<![A-Za-z0-9])<(?:[a-z][a-z0-9-]*|[A-Z][A-Z0-9-]+)"
    r"(?:[\s/]+[A-Za-z_:@-][\w:.-]*\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'=<>`]+))*"
    r"[\s/]*>"
    r"|</[A-Za-z][A-Za-z0-9-]*\s*>"
)


def strip_html_tags(value):
    return _HTML_TAG.sub("", str(value or ""))


def clean_text(value, maximum=3000):
    value = strip_html_tags(value)
    return re.sub(r"\s+", " ", value).strip()[:maximum]


def client_ip(request):
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.remote_addr) or "unknown"

