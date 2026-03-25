(function () {
  "use strict";

  const form = document.getElementById("reqForm");
  if (!form) return;

  const container = document.getElementById("formsetContainer");
  const addBtn = document.getElementById("btnAddLine");
  const emptyTemplate = document.getElementById("emptyFormTemplate");
  const totalFormsInput =
    document.getElementById("id_lignes-TOTAL_FORMS") ||
    document.getElementById("id_lignerequisition_set-TOTAL_FORMS") ||
    document.querySelector('input[name$="-TOTAL_FORMS"]');
  const submitButtons = Array.from(form.querySelectorAll('button[type="submit"]'));

  if (!container || !addBtn || !emptyTemplate || !totalFormsInput) return;

  function getFormsetPrefix() {
    const name = totalFormsInput.getAttribute("name") || "";
    return name.replace("-TOTAL_FORMS", "");
  }

  const formsetPrefix = getFormsetPrefix();

  function safeParseJSON(value, fallback) {
    try {
      return JSON.parse(value);
    } catch (err) {
      return fallback;
    }
  }

  function normalizeText(value) {
    return String(value || "").trim().toLowerCase();
  }

  function pluralize(count, singular, plural) {
    return Number(count) === 1 ? singular : plural;
  }

  function getRowElements(row) {
    return {
      articleSelect: row.querySelector(
        `select[name^="${formsetPrefix}-"][name$="-article"]`
      ),
      uniteSelect: row.querySelector(
        `select[name^="${formsetPrefix}-"][name$="-unite_demandee"]`
      ),
      qtyInput: row.querySelector(
        `input[name^="${formsetPrefix}-"][name$="-quantite_demandee"]`
      ),
      motifInput: row.querySelector(
        `textarea[name^="${formsetPrefix}-"][name$="-motif_article"]`
      ),
      deleteInput: row.querySelector(
        `input[name^="${formsetPrefix}-"][name$="-DELETE"]`
      ),
      stockHelp: row.querySelector(".js-stock-help"),
      unitHelp: row.querySelector(".js-unit-help"),
      qtyHelp: row.querySelector(".js-qty-help"),
      lineSummary: row.querySelector(".js-line-summary"),
      removeBtn: row.querySelector(".js-remove-row"),
    };
  }

  function getArticleMetaMap(articleSelect) {
    if (!articleSelect) return {};
    const raw =
      articleSelect.getAttribute("data-article-meta-map") ||
      articleSelect.dataset.articleMetaMap ||
      "{}";
    return safeParseJSON(raw, {});
  }

  function getArticleMeta(articleSelect) {
    if (!articleSelect) return null;
    const metaMap = getArticleMetaMap(articleSelect);
    const articleId = String(articleSelect.value || "").trim();
    return metaMap[articleId] || null;
  }

  function clearSelectOptions(selectEl) {
    if (!selectEl) return;
    while (selectEl.options.length > 0) {
      selectEl.remove(0);
    }
  }

  function buildOption(value, label, selected) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (selected) option.selected = true;
    return option;
  }

  function getDefaultAllowedUnits(articleMeta) {
    if (!articleMeta) {
      return ["Unité"];
    }

    if (
      Array.isArray(articleMeta.unites_autorisees) &&
      articleMeta.unites_autorisees.length > 0
    ) {
      return articleMeta.unites_autorisees;
    }

    const mainUnit = String(articleMeta.unite_principale || "").trim();
    if (!mainUnit || normalizeText(mainUnit) === "unité" || normalizeText(mainUnit) === "unite") {
      return ["Unité"];
    }

    return ["Unité", mainUnit];
  }

  function fillUniteOptions(uniteSelect, articleMeta, selectedValue) {
    if (!uniteSelect) return;

    const currentSelected = String(selectedValue || uniteSelect.value || "Unité").trim() || "Unité";
    clearSelectOptions(uniteSelect);

    const allowed = getDefaultAllowedUnits(articleMeta);

    allowed.forEach((unite, index) => {
      const selected =
        allowed.includes(currentSelected) ? currentSelected === unite : index === 0;
      uniteSelect.appendChild(buildOption(unite, unite, selected));
    });

    uniteSelect.disabled = !articleMeta;
  }

  function hideQtyHelp(qtyHelp) {
    if (!qtyHelp) return;
    qtyHelp.textContent = "Il y a pas cette quantité en stock";
    qtyHelp.classList.add("d-none");
    qtyHelp.classList.remove("text-danger");
  }

  function showQtyHelp(qtyHelp, message) {
    if (!qtyHelp) return;
    qtyHelp.textContent = message || "Il y a pas cette quantité en stock";
    qtyHelp.classList.remove("d-none");
    qtyHelp.classList.add("text-danger");
  }

  function formatStockHelp(articleMeta) {
    if (!articleMeta) {
      return "Sélectionnez un article.";
    }

    const conditionnement =
      articleMeta.libelle_conditionnement ||
      articleMeta.resume_conditionnement ||
      articleMeta.unite_principale ||
      "—";

    if (articleMeta.est_disponible) {
      return `Article disponible. Conditionnement : ${conditionnement}.`;
    }

    return `Article indisponible. Conditionnement : ${conditionnement}.`;
  }

  function formatUnitHelp(articleMeta) {
    if (!articleMeta) {
      return "Choisissez Unité ou le conditionnement de stockage.";
    }

    if (articleMeta.est_stocke_par_unite) {
      return "Cet article est géré uniquement à l’unité.";
    }

    const allowed = getDefaultAllowedUnits(articleMeta).join(" / ");
    return `Choix disponibles : ${allowed}.`;
  }

  function computeEquivalentUnits(articleMeta, unite, qty) {
    if (!articleMeta) return 0;

    const quantity = Number(qty || 0);
    if (!Number.isFinite(quantity) || quantity <= 0) return 0;

    const qpc = Number(articleMeta.quantite_par_conditionnement || 1);
    const normalizedUnit = normalizeText(unite);
    const normalizedMain = normalizeText(articleMeta.unite_principale || "");

    if (!normalizedUnit || normalizedUnit === "unité" || normalizedUnit === "unite") {
      return quantity;
    }

    if (normalizedUnit === normalizedMain) {
      return quantity * qpc;
    }

    return quantity;
  }

  function labelWithPlural(unit, qty) {
    const text = String(unit || "").trim();
    if (!text) return qty > 1 ? "unités" : "unité";
    if (qty <= 1) return text;
    if (text.toLowerCase().endsWith("s")) return text;
    return `${text}s`;
  }

  function formatEquivalentSummary(articleMeta, unite, qty, eqUnits) {
    if (!articleMeta) {
      return "La conversion réelle sera calculée automatiquement selon l’article choisi.";
    }

    if (!qty || qty <= 0) {
      return `Conditionnement disponible : ${articleMeta.libelle_conditionnement || articleMeta.resume_conditionnement || "—"}.`;
    }

    return (
      `${qty} ${labelWithPlural(unite, qty)} = ${eqUnits} ` +
      `${pluralize(eqUnits, "unité réelle", "unités réelles")}.`
    );
  }

  function setSubmitState(disabled) {
    submitButtons.forEach((btn) => {
      btn.disabled = !!disabled;
    });
  }

  function rowHasVisibleQtyError(row) {
    const { qtyHelp } = getRowElements(row);
    return !!(qtyHelp && !qtyHelp.classList.contains("d-none"));
  }

  function formHasBlockingError() {
    const rows = Array.from(container.querySelectorAll(".formset-item"));
    return rows.some((row) => rowHasVisibleQtyError(row));
  }

  function refreshSubmitState() {
    setSubmitState(formHasBlockingError());
  }

  function renderLineSummary(row) {
    const {
      articleSelect,
      uniteSelect,
      qtyInput,
      lineSummary,
      stockHelp,
      unitHelp,
    } = getRowElements(row);

    if (!lineSummary) return;

    const articleMeta = getArticleMeta(articleSelect);

    if (stockHelp) {
      stockHelp.textContent = formatStockHelp(articleMeta);
      stockHelp.classList.remove("text-danger", "text-success");

      if (articleMeta) {
        if (articleMeta.est_disponible) {
          stockHelp.classList.add("text-success");
        } else {
          stockHelp.classList.add("text-danger");
        }
      }
    }

    if (unitHelp) {
      unitHelp.textContent = formatUnitHelp(articleMeta);
    }

    if (!articleMeta) {
      lineSummary.textContent =
        "La conversion réelle sera calculée automatiquement selon l’article choisi.";
      row.classList.remove("req-row-out-of-stock", "req-row-in-stock");
      return;
    }

    if (!articleMeta.est_disponible) {
      row.classList.add("req-row-out-of-stock");
      row.classList.remove("req-row-in-stock");
      lineSummary.textContent = "Cet article est actuellement indisponible.";
      return;
    }

    row.classList.add("req-row-in-stock");
    row.classList.remove("req-row-out-of-stock");

    const qty = Number(qtyInput?.value || 0);
    const unite = String(uniteSelect?.value || "Unité").trim() || "Unité";
    const eqUnits = computeEquivalentUnits(articleMeta, unite, qty);

    lineSummary.textContent = formatEquivalentSummary(articleMeta, unite, qty, eqUnits);
  }

  function validateQtyInput(row) {
    const { articleSelect, uniteSelect, qtyInput, qtyHelp } = getRowElements(row);
    if (!articleSelect || !qtyInput) return true;

    const articleId = String(articleSelect.value || "").trim();
    const articleMeta = getArticleMeta(articleSelect);

    if (!articleId) {
      qtyInput.disabled = false;
      hideQtyHelp(qtyHelp);
      refreshSubmitState();
      return true;
    }

    if (!articleMeta) {
      qtyInput.disabled = false;
      hideQtyHelp(qtyHelp);
      refreshSubmitState();
      return true;
    }

    const stockUnites = Number(articleMeta.stock_actuel_unites || 0);
    const raw = String(qtyInput.value || "").trim();

    if (stockUnites <= 0) {
      qtyInput.value = "";
      qtyInput.disabled = true;
      showQtyHelp(qtyHelp, "Article indisponible.");
      refreshSubmitState();
      return false;
    }

    qtyInput.disabled = false;

    if (!raw) {
      hideQtyHelp(qtyHelp);
      refreshSubmitState();
      return true;
    }

    const qty = Number(raw);
    if (!Number.isFinite(qty) || qty < 1) {
      qtyInput.value = "";
      hideQtyHelp(qtyHelp);
      refreshSubmitState();
      return false;
    }

    const unite = String(uniteSelect?.value || "Unité").trim() || "Unité";
    const eqUnits = computeEquivalentUnits(articleMeta, unite, qty);

    if (eqUnits > stockUnites) {
      showQtyHelp(qtyHelp, "Il y a pas cette quantité en stock");
      refreshSubmitState();
      return false;
    }

    hideQtyHelp(qtyHelp);
    refreshSubmitState();
    return true;
  }

  function setArticleOptionStates(articleSelect) {
    if (!articleSelect) return;

    const metaMap = getArticleMetaMap(articleSelect);

    Array.from(articleSelect.options).forEach((option) => {
      const value = String(option.value || "").trim();
      if (!value) return;

      const meta = metaMap[value];
      const stockUnites = Number(meta?.stock_actuel_unites || 0);
      const isOut = stockUnites <= 0;

      const baseLabel =
        option.dataset.baseLabel ||
        option.textContent.replace(/\s+—\s+Indisponible$/i, "").trim();

      option.dataset.baseLabel = baseLabel;
      option.textContent = isOut ? `${baseLabel} — Indisponible` : baseLabel;
      option.dataset.outOfStock = isOut ? "1" : "0";
      option.disabled = isOut;
    });

    const currentOption = articleSelect.options[articleSelect.selectedIndex];
    if (currentOption && currentOption.disabled) {
      articleSelect.value = "";
    }
  }
  function updateRowState(row) {
    const { articleSelect, uniteSelect, qtyInput, qtyHelp } = getRowElements(row);
    if (!articleSelect || !uniteSelect || !qtyInput) return;

    setArticleOptionStates(articleSelect);

    const articleMeta = getArticleMeta(articleSelect);
    const selectedUnit =
      uniteSelect.getAttribute("data-selected") ||
      uniteSelect.dataset.defaultValue ||
      uniteSelect.value ||
      "Unité";

    fillUniteOptions(uniteSelect, articleMeta, selectedUnit);

    if (!articleMeta) {
      qtyInput.disabled = false;
      hideQtyHelp(qtyHelp);
      renderLineSummary(row);
      refreshSubmitState();
      return;
    }

    const stockUnites = Number(articleMeta.stock_actuel_unites || 0);

    if (stockUnites <= 0) {
      qtyInput.value = "";
      qtyInput.disabled = true;
      showQtyHelp(qtyHelp, "Article indisponible.");
      renderLineSummary(row);
      refreshSubmitState();
      return;
    }

    qtyInput.disabled = false;
    hideQtyHelp(qtyHelp);
    validateQtyInput(row);
    renderLineSummary(row);
    refreshSubmitState();
  }

  function attachRowEvents(row) {
    const { articleSelect, uniteSelect, qtyInput, removeBtn } = getRowElements(row);

    if (articleSelect) {
      setArticleOptionStates(articleSelect);

      articleSelect.addEventListener("change", function () {
        if (uniteSelect) {
          uniteSelect.setAttribute("data-selected", "Unité");
        }
        updateRowState(row);
      });
    }

    if (uniteSelect) {
      uniteSelect.addEventListener("change", function () {
        uniteSelect.setAttribute("data-selected", uniteSelect.value || "Unité");
        validateQtyInput(row);
        renderLineSummary(row);
      });
    }

    if (qtyInput) {
      qtyInput.addEventListener("input", function () {
        validateQtyInput(row);
        renderLineSummary(row);
      });

      qtyInput.addEventListener("blur", function () {
        validateQtyInput(row);
        renderLineSummary(row);
      });
    }

    if (removeBtn) {
      removeBtn.addEventListener("click", function () {
        removeRow(row);
      });
    }

    updateRowState(row);
  }

  function refreshIndexes() {
    const rows = Array.from(container.querySelectorAll(".formset-item"));

    rows.forEach((row, index) => {
      const regex = new RegExp(`${formsetPrefix}-(\\d+|__prefix__)`, "g");

      row.querySelectorAll("input, select, textarea, label").forEach((element) => {
        ["name", "id", "for"].forEach((attr) => {
          const value = element.getAttribute(attr);
          if (value) {
            element.setAttribute(attr, value.replace(regex, `${formsetPrefix}-${index}`));
          }
        });
      });
    });

    totalFormsInput.value = String(rows.length);
  }

  function createRowFromTemplate() {
    const templateItem = emptyTemplate.querySelector(".formset-item");
    if (!templateItem) return null;

    const clone = templateItem.cloneNode(true);
    const index = Number(totalFormsInput.value || 0);
    const regex = new RegExp(`${formsetPrefix}-__prefix__`, "g");

    clone.querySelectorAll("input, select, textarea, label").forEach((element) => {
      ["name", "id", "for"].forEach((attr) => {
        const value = element.getAttribute(attr);
        if (value) {
          element.setAttribute(attr, value.replace(regex, `${formsetPrefix}-${index}`));
        }
      });
    });

    clone.querySelectorAll("input, textarea").forEach((element) => {
      const type = (element.getAttribute("type") || "").toLowerCase();

      if (type === "checkbox" || type === "radio") {
        element.checked = false;
      } else if (type !== "hidden") {
        element.value = "";
      }
    });

    clone.querySelectorAll("select").forEach((element) => {
      if (element.name && element.name.endsWith("-unite_demandee")) {
        clearSelectOptions(element);
        element.appendChild(buildOption("Unité", "Unité", true));
        element.setAttribute("data-selected", "Unité");
        element.disabled = true;
      } else {
        element.selectedIndex = 0;
      }
    });

    const qtyHelp = clone.querySelector(".js-qty-help");
    hideQtyHelp(qtyHelp);

    const stockHelp = clone.querySelector(".js-stock-help");
    if (stockHelp) {
      stockHelp.textContent = "Sélectionnez un article.";
      stockHelp.classList.remove("text-danger", "text-success");
    }

    const unitHelp = clone.querySelector(".js-unit-help");
    if (unitHelp) {
      unitHelp.textContent = "Choisissez Unité ou le conditionnement de stockage.";
    }

    const lineSummary = clone.querySelector(".js-line-summary");
    if (lineSummary) {
      lineSummary.textContent =
        "La conversion réelle sera calculée automatiquement selon l’article choisi.";
    }

    return clone;
  }

  function addRow() {
    const row = createRowFromTemplate();
    if (!row) return;

    container.appendChild(row);
    refreshIndexes();
    attachRowEvents(row);
    refreshSubmitState();
  }

  function removeRow(row) {
    const rows = Array.from(container.querySelectorAll(".formset-item"));

    if (rows.length <= 1) {
      const { articleSelect, uniteSelect, qtyInput, motifInput, deleteInput, qtyHelp } =
        getRowElements(row);

      if (articleSelect) articleSelect.value = "";
      if (uniteSelect) {
        clearSelectOptions(uniteSelect);
        uniteSelect.appendChild(buildOption("Unité", "Unité", true));
        uniteSelect.disabled = true;
        uniteSelect.setAttribute("data-selected", "Unité");
      }
      if (qtyInput) {
        qtyInput.value = "";
        qtyInput.disabled = false;
      }
      if (motifInput) motifInput.value = "";
      if (deleteInput) deleteInput.checked = false;

      hideQtyHelp(qtyHelp);
      updateRowState(row);
      refreshSubmitState();
      return;
    }

    const deleteInput = row.querySelector(`input[name^="${formsetPrefix}-"][name$="-DELETE"]`);
    if (deleteInput) {
      deleteInput.checked = true;
    }

    row.remove();
    refreshIndexes();

    Array.from(container.querySelectorAll(".formset-item")).forEach((item) => {
      attachRowEvents(item);
    });

    refreshSubmitState();
  }

  addBtn.addEventListener("click", addRow);

  Array.from(container.querySelectorAll(".formset-item")).forEach((row) => {
    attachRowEvents(row);
  });

  form.addEventListener("submit", function (event) {
    const rows = Array.from(container.querySelectorAll(".formset-item"));
    let hasError = false;

    rows.forEach((row) => {
      const valid = validateQtyInput(row);
      renderLineSummary(row);
      if (!valid && rowHasVisibleQtyError(row)) {
        hasError = true;
      }
    });

    refreshSubmitState();

    if (hasError) {
      event.preventDefault();
    }
  });

  refreshSubmitState();
})();