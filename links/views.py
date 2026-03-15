from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect

from .models import ShortLink


INDEX_HTML = """
<!doctype html>
<html lang=\"en\">
  <head>
    <meta charset=\"utf-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
    <title>Django Link Shortener</title>
    <style>
      body { font-family: system-ui, sans-serif; max-width: 720px; margin: 4rem auto; padding: 0 1rem; line-height: 1.5; }
      code { background: #f4f4f4; padding: 0.15rem 0.35rem; border-radius: 4px; }
    </style>
  </head>
  <body>
    <h1>Django Link Shortener</h1>
    <p>The service is running.</p>
    <p>Create short links in <a href=\"/admin/\">Django admin</a>.</p>
    <p>Short links are available at <code>/&lt;code&gt;/</code>.</p>
  </body>
</html>
"""


def index(request):
    return HttpResponse(INDEX_HTML)


def redirect_short_link(request, code):
    link = get_object_or_404(ShortLink, short_code=code.lower(), is_active=True)
    return redirect(link.target_url)
