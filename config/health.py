from django.db import DatabaseError
from django.http import JsonResponse
from django.views.decorators.http import require_safe

from links.models import ShortLink


@require_safe
def ready(request):
    """Check that the application can read its migrated database."""
    try:
        ShortLink.objects.exists()
    except DatabaseError:
        response = JsonResponse({'status': 'unavailable'}, status=503)
    else:
        response = JsonResponse({'status': 'ok'})
    response['Cache-Control'] = 'no-store'
    return response
