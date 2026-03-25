from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.utils.timezone import localtime

from audit.models import AuditLog
from audit.services import audit_log as enregistrer_audit
from requisitions.models import Requisition

from .models import Notification


def _audit_lecture_notification(request, notif: Notification) -> None:
    try:
        enregistrer_audit(
            action=AuditLog.Action.LECTURE_NOTIFICATION,
            user=request.user,
            request=request,
            app_label="notifications",
            cible_type="Notification",
            cible_id=str(notif.pk),
            cible_label=(notif.titre or "Notification").strip() or f"Notification #{notif.pk}",
            message="Lecture d'une notification.",
            meta={
                "notification_id": notif.pk,
                "lu": notif.lu,
                "date_lecture": str(notif.date_lecture) if notif.date_lecture else "",
                "requisition_id": getattr(notif.requisition, "pk", None),
            },
            identifiant_saisi=getattr(request.user, "email", "") or "",
        )
    except Exception:
        pass


@login_required
def liste(request):
    qs = Notification.objects.filter(destinataire=request.user)

    filtre = (request.GET.get("filtre") or "").strip().lower()
    if filtre == "non_lues":
        qs = qs.filter(lu=False)
    elif filtre == "lues":
        qs = qs.filter(lu=True)

    q = (request.GET.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(message__icontains=q) | Q(titre__icontains=q))

    qs = qs.select_related("requisition").order_by("-date_creation", "-id")

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    nb_non_lues = Notification.objects.filter(destinataire=request.user, lu=False).count()

    try:
        enregistrer_audit(
            action=AuditLog.Action.CONSULTATION_NOTIFICATIONS,
            user=request.user,
            request=request,
            app_label="notifications",
            message="Consultation de la liste des notifications.",
            meta={
                "filtre": filtre,
                "q": q,
                "nombre_resultats_page": len(page_obj.object_list),
                "page": page_obj.number,
                "nb_non_lues": nb_non_lues,
            },
            identifiant_saisi=getattr(request.user, "email", "") or "",
        )
    except Exception:
        pass

    ctx = {
        "notifications": page_obj.object_list,
        "page_obj": page_obj,
        "filtre": filtre,
        "q": q,
        "nb_non_lues": nb_non_lues,
    }
    return render(request, "notifications/liste.html", ctx)


@login_required
def ouvrir(request, id: int):
    notif = get_object_or_404(
        Notification.objects.select_related("requisition"),
        pk=id,
        destinataire=request.user,
    )

    notif.marquer_lu()
    _audit_lecture_notification(request, notif)

    if notif.requisition_id:
        req = notif.requisition

        if req:
            if req.etat_requisition == Requisition.ETAT_TRAITEE:
                messages.info(request, "Cette réquisition a déjà été traitée.")

            url = reverse("requisitions:detail", kwargs={"pk": req.pk})
            return redirect(f"{url}?source=notification&notification_id={notif.pk}#zone-actions")

    messages.info(request, "Aucun objet lié à cette notification.")
    return redirect(reverse("notifications:liste"))


@login_required
def marquer_lu(request, id: int):
    notif = get_object_or_404(Notification, pk=id, destinataire=request.user)
    notif.marquer_lu()
    _audit_lecture_notification(request, notif)

    messages.success(request, "Notification marquée comme lue.")
    return redirect(reverse("notifications:liste"))


@require_POST
@login_required
def supprimer_selection(request):
    ids = request.POST.getlist("notification_ids")

    if not ids:
        messages.warning(request, "Veuillez sélectionner au moins une notification à supprimer.")
        return redirect(reverse("notifications:liste"))

    qs = Notification.objects.filter(destinataire=request.user, id__in=ids)
    nb = qs.count()

    if nb == 0:
        messages.warning(request, "Aucune notification valide à supprimer.")
        return redirect(reverse("notifications:liste"))

    qs.delete()
    messages.success(request, f"{nb} notification(s) supprimée(s).")
    return redirect(reverse("notifications:liste"))


@require_POST
@login_required
def supprimer_lues(request):
    qs = Notification.objects.filter(destinataire=request.user, lu=True)
    nb = qs.count()

    if nb == 0:
        messages.warning(request, "Aucune notification lue à supprimer.")
        return redirect(reverse("notifications:liste"))

    qs.delete()
    messages.success(request, f"{nb} notification(s) lue(s) supprimée(s).")
    return redirect(reverse("notifications:liste"))


# =========================
# Notification live
# =========================
@login_required
def notifications_live(request):
    qs = (
        Notification.objects
        .filter(destinataire=request.user)
        .select_related("requisition")
        .order_by("-date_creation")[:5]
    )

    data = []
    for n in qs:
        data.append({
            "id": n.pk,
            "titre": n.titre,
            "message": n.message,
            "lu": n.lu,
            "date": localtime(n.date_creation).strftime("%d/%m %H:%M"),
            "url": reverse("notifications:ouvrir", args=[n.pk]),
        })

    nb_non_lues = Notification.objects.filter(
        destinataire=request.user,
        lu=False
    ).count()

    return JsonResponse({
        "notifications": data,
        "nb_non_lues": nb_non_lues,
    })