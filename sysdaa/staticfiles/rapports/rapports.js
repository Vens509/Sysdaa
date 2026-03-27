(function () {
  "use strict";

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function parseConfig() {
    const el = document.getElementById("rp-config-data");
    if (!el) return null;

    try {
      return JSON.parse(el.textContent || "{}");
    } catch (error) {
      return null;
    }
  }

  function show(el) {
    if (!el) return;
    el.classList.remove("d-none");
    el.style.display = "";
  }

  function hide(el) {
    if (!el) return;
    el.classList.add("d-none");
    el.style.display = "none";
  }

  function normalizeText(value) {
    return String(value || "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .trim();
  }

  function countVisibleRows(rows) {
    return rows.reduce(function (acc, row) {
      return acc + (row.style.display === "none" ? 0 : 1);
    }, 0);
  }

  function getFieldWrap(input) {
    if (!input) return null;
    return input.closest(".rp-field");
  }

  function isPlaceholderValue(value) {
    return String(value || "").trim() === "";
  }

  function getCurrentFormState(nodes) {
    return {
      periode: nodes.periode ? String(nodes.periode.value || "").trim() : "",
      typeRapport: nodes.typeRapport ? String(nodes.typeRapport.value || "").trim() : "",
      categorie: nodes.categorie ? String(nodes.categorie.value || "").trim() : "",
      direction: nodes.direction ? String(nodes.direction.value || "").trim() : "",
      etatRequisition: nodes.etatRequisition ? String(nodes.etatRequisition.value || "").trim() : ""
    };
  }

  function setFieldEnabled(input, enabled) {
    if (!input) return;

    const wrap = getFieldWrap(input);
    const label = wrap ? qs("label", wrap) : null;

    input.disabled = !enabled;
    input.setAttribute("aria-disabled", enabled ? "false" : "true");

    if (!enabled && input.tagName === "SELECT") {
      input.value = "";
    }

    if (wrap) {
      wrap.classList.toggle("rp-field--disabled", !enabled);
      wrap.style.opacity = enabled ? "" : "0.7";
      wrap.style.pointerEvents = enabled ? "" : "";
    }

    if (label) {
      label.classList.toggle("text-muted", !enabled);
    }
  }

  function syncMoisVisibility(nodes, state) {
    const isAnnual = state.periode === "ANNUEL";

    if (isAnnual) {
      hide(nodes.moisWrap);
      if (nodes.mois) {
        nodes.mois.value = "";
      }
    } else {
      show(nodes.moisWrap);
    }
  }

  function syncFieldInterdependence(nodes) {
    const state = getCurrentFormState(nodes);
    const effectiveType = state.typeRapport || "stock_global";

    syncMoisVisibility(nodes, state);

    setFieldEnabled(nodes.categorie, true);
    setFieldEnabled(nodes.direction, true);
    setFieldEnabled(nodes.etatRequisition, true);

    if (effectiveType === "stock_global" && !isPlaceholderValue(state.etatRequisition)) {
      setFieldEnabled(nodes.categorie, false);
      setFieldEnabled(nodes.direction, false);
      return;
    }

    if (
      effectiveType === "direction" ||
      effectiveType === "direction_plus_demandeuse" ||
      effectiveType === "direction_moins_demandeuse"
    ) {
      setFieldEnabled(nodes.direction, false);
    }

    if (
      effectiveType === "direction_plus_demandeuse" ||
      effectiveType === "direction_moins_demandeuse" ||
      effectiveType === "article_plus_demande" ||
      effectiveType === "article_moins_demande"
    ) {
      setFieldEnabled(nodes.etatRequisition, false);
    }

    if (effectiveType === "categorie_article") {
      setFieldEnabled(nodes.categorie, false);
    }
  }

  function bindFormBehavior(nodes) {
    [
      nodes.periode,
      nodes.typeRapport,
      nodes.categorie,
      nodes.direction,
      nodes.etatRequisition
    ].forEach(function (input) {
      if (!input) return;

      input.addEventListener("change", function () {
        syncFieldInterdependence(nodes);
      });
    });

    syncFieldInterdependence(nodes);
  }

  function bindTableSearch(nodes) {
    if (!nodes.tableSearch || !nodes.table) return;

    const tbody = qs("tbody", nodes.table);
    if (!tbody) return;

    const rows = qsa("tr", tbody);
    if (!rows.length) return;

    nodes.tableSearch.addEventListener("input", function () {
      const term = normalizeText(nodes.tableSearch.value);

      rows.forEach(function (row) {
        const text = normalizeText(row.textContent);
        const visible = !term || text.indexOf(term) !== -1;
        row.style.display = visible ? "" : "none";
      });

      const visibleCount = countVisibleRows(rows);
      if (visibleCount === 0) {
        show(nodes.tableEmptySearch);
      } else {
        hide(nodes.tableEmptySearch);
      }
    });
  }

  function init() {
    const config = parseConfig();
    if (!config || !config.selectors) return;

    const form = qs("#rapportForm");

    const nodes = {
      form: form,
      periode: qs(config.selectors.periode),
      moisWrap: qs(config.selectors.moisWrap),
      mois: form ? qs('[data-role="mois"]', form) : null,
      typeRapport: form ? qs('[data-role="type-rapport"]', form) : null,
      categorie: form ? qs('[data-role="categorie"]', form) : null,
      direction: form ? qs('[data-role="direction"]', form) : null,
      etatRequisition: form ? qs('[data-role="etat-requisition"]', form) : null,
      tableSearch: qs(config.selectors.tableSearch),
      table: qs(config.selectors.table),
      tableEmptySearch: qs(config.selectors.tableEmptySearch)
    };

    bindFormBehavior(nodes);
    bindTableSearch(nodes);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();