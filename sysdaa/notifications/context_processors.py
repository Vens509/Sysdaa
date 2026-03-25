from __future__ import annotations

from .models import Notification


def notif_unread_count(request):
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return {"notif_unread_count": 0}

    c = Notification.objects.filter(destinataire=user, lu=False).count()
    return {"notif_unread_count": c}