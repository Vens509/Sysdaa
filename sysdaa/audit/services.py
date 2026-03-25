from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from django.utils import timezone

from .models import AuditLog


@dataclass(frozen=True)
class AuditResultat:
    audit_id: int


def _safe_str(v: Any, max_len: int = 200) -> str:
    s = "" if v is None else str(v)
    s = s.strip()
    if len(s) > max_len:
        s = s[: max_len - 1] + "…"
    return s


def _extraire_identifiant_saisi(*, identifiant_saisi=None, acteur=None, request=None, details=None) -> str:
    if identifiant_saisi:
        return _safe_str(identifiant_saisi, 150)

    if isinstance(details, dict):
        for key in ("identifiant_saisi", "email", "username", "login"):
            value = details.get(key)
            if value:
                return _safe_str(value, 150)

    if acteur is not None:
        email = getattr(acteur, "email", "") or ""
        if email:
            return _safe_str(email, 150)

    if request is not None:
        for key in ("email", "username", "identifiant", "login"):
            value = request.POST.get(key) or request.GET.get(key)
            if value:
                return _safe_str(value, 150)

    return ""


def _looks_like_default_object_repr(value: str) -> bool:
    s = (value or "").strip()
    return s.startswith("<") and " object at " in s and s.endswith(">")


def _premiere_valeur_non_vide(obj: Any, *attrs: str) -> str:
    for attr in attrs:
        try:
            value = getattr(obj, attr, None)
        except Exception:
            value = None

        if value is None:
            continue

        value = _safe_str(value, 200)
        if value:
            return value
    return ""


def _extraire_cible_label(cible: Any) -> str:
    if cible is None:
        return ""

    try:
        nom = _safe_str(getattr(cible, "nom", ""), 120)
        prenom = _safe_str(getattr(cible, "prenom", ""), 120)
        if nom and prenom:
            return _safe_str(f"{prenom} {nom}", 200)
        if nom:
            return _safe_str(nom, 200)
    except Exception:
        pass

    for attr in (
        "libelle",
        "titre",
        "label",
        "intitule",
        "intitulé",
        "designation",
        "désignation",
        "nom_role",
        "nom_permission",
        "code",
        "reference",
        "référence",
        "numero",
        "numéro",
        "email",
    ):
        value = _premiere_valeur_non_vide(cible, attr)
        if value:
            return _safe_str(value, 200)

    try:
        rendered = _safe_str(cible, 200)
        if rendered and not _looks_like_default_object_repr(rendered):
            return rendered
    except Exception:
        pass

    return ""


def audit_log(
    *,
    app: str = "",
    action: str,
    acteur=None,
    app_label: str = "",
    user=None,
    niveau: str = AuditLog.Niveau.INFO,
    succes: bool = True,
    message: str = "",
    details: Optional[dict[str, Any]] = None,
    model: str = "",
    object_id: str = "",
    meta: Optional[dict[str, Any]] = None,
    cible=None,
    request=None,
    cible_type: str = "",
    cible_id: str = "",
    cible_label: str = "",
    identifiant_saisi: str = "",
    **extra,
) -> AuditResultat:
    """
    Journalisation centralisée et rétro-compatible.

    Compat :
    - user => acteur
    - app_label si app vide
    - model/object_id => cible_type/cible_id
    - meta fusionné dans details
    - extra absorbé sans casser
    """
    app_final = (app or "").strip() or (app_label or "").strip()

    if acteur is None and user is not None:
        acteur = user

    det: dict[str, Any] = {}
    if isinstance(details, dict):
        det.update(details)
    if isinstance(meta, dict):
        det.update(meta)
    if extra:
        det.setdefault("_extra", {})
        det["_extra"].update({k: v for k, v in extra.items()})

    ip = None
    ua = ""
    if request is not None:
        try:
            ip = (
                request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
                or request.META.get("REMOTE_ADDR")
            )
        except Exception:
            ip = None

        try:
            ua = _safe_str(request.META.get("HTTP_USER_AGENT", ""), 300)
        except Exception:
            ua = ""

    if model and not cible_type:
        cible_type = model
    if object_id and not cible_id:
        cible_id = object_id

    if cible is not None:
        try:
            cible_type = cible_type or cible.__class__.__name__
            cible_id = cible_id or _safe_str(getattr(cible, "pk", "") or getattr(cible, "id", ""), 64)
            cible_label = cible_label or _extraire_cible_label(cible)
        except Exception:
            pass

    if not cible_label and cible_id:
        cible_label = _safe_str(cible_id, 200)

    identifiant_final = _extraire_identifiant_saisi(
        identifiant_saisi=identifiant_saisi,
        acteur=acteur,
        request=request,
        details=det,
    )

    log = AuditLog.objects.create(
        date_action=timezone.now(),
        niveau=niveau,
        app=_safe_str(app_final, 80),
        action=_safe_str(action, 80),
        acteur=acteur if getattr(acteur, "pk", None) else None,
        identifiant_saisi=identifiant_final,
        ip=ip,
        user_agent=ua,
        cible_type=_safe_str(cible_type, 120),
        cible_id=_safe_str(cible_id, 64),
        cible_label=_safe_str(cible_label, 200),
        message=_safe_str(message, 250),
        details=det,
        succes=bool(succes),
    )

    return AuditResultat(audit_id=log.id)


enregistrer_audit = audit_log