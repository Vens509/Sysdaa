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
      categorySelect: row.querySelector(
        `select[name^="${formsetPrefix}-"][name$="-categorie_article"]`
      ),
      articleSelect: row.querySelector(
        `select[name^="${formsetPrefix}-"][name$="-article"]`
      ),
      articleSelectWrap: row.querySelector(".js-article-select-wrap"),
      articleSearchWrap: row.querySelector(".js-article-search-wrap"),
      articleSearchInput: row.querySelector(".js-article-search-input"),
      articleSearchResults: row.querySelector(".js-article-search-results"),
      articleSearchButtons: row.querySelectorAll(".js-toggle-article-search"),
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

  function getAllArticlesMeta(articleSelect) {
    const metaMap = getArticleMetaMap(articleSelect);
    return Object.keys(metaMap)
      .map((key) => metaMap[key])
      .filter(Boolean)
      .sort((a, b) =>
        String(a.nom || "").localeCompare(String(b.nom || ""), "fr", {
          sensitivity: "base",
        })
      );
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

    const currentSelected =
      String(selectedValue || uniteSelect.value || "Unité").trim() || "Unité";
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

    const stock = Number(articleMeta.stock_actuel_unites || 0);
    if (stock <= 0) {
      return "Stock actuel : 0 unité.";
    }

    return (
      `Stock actuel : ${stock} ${pluralize(stock, "unité", "unités")}. ` +
      `${articleMeta.resume_conditionnement || ""}`.trim()
    );
  }

  function formatUnitHelp(articleMeta) {
    if (!articleMeta) {
      return "Choisissez Unité ou le conditionnement de stockage.";
    }

    const allowed = getDefaultAllowedUnits(articleMeta);
    if (allowed.length <= 1) {
      return "Cet article se demande uniquement en Unité.";
    }

    return `Choix autorisés : ${allowed.join(" ou ")}.`;
  }

  function computeEquivalentUnits(articleMeta, unite, quantity) {
    const qty = Number(quantity || 0);
    if (!articleMeta || !Number.isFinite(qty) || qty <= 0) {
      return 0;
    }

    const qpc = Number(articleMeta.quantite_par_conditionnement || 1);
    const normalizedUnit = normalizeText(unite);
    const normalizedMain = normalizeText(articleMeta.unite_principale || "");

    if (!normalizedUnit || normalizedUnit === "unité" || normalizedUnit === "unite") {
      return qty;
    }

    if (normalizedUnit === normalizedMain) {
      return qty * qpc;
    }

    return qty;
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

  function articleMatchesCategory(meta, categoryValue) {
    const wanted = normalizeText(categoryValue);
    if (!wanted) return true;
    return normalizeText(meta?.categorie_key || meta?.categorie || "") === wanted;
  }

  function articleMatchesSearch(meta, searchValue) {
    const term = normalizeText(searchValue);
    if (!term) return true;

    const articleName = normalizeText(meta?.nom || "");
    return articleName.startsWith(term);
  }

  function getSelectedArticleIds(exceptRow = null) {
    const ids = new Set();

    const rows = Array.from(container.querySelectorAll(".formset-item"));
    rows.forEach((row) => {
      if (exceptRow && row === exceptRow) return;

      const { articleSelect, deleteInput } = getRowElements(row);
      if (deleteInput && deleteInput.checked) return;
      if (!articleSelect) return;

      const value = String(articleSelect.value || "").trim();
      if (value) {
        ids.add(value);
      }
    });

    return ids;
  }

  function isArticleAlreadyUsed(articleId, currentRow) {
    if (!articleId) return false;
    return getSelectedArticleIds(currentRow).has(String(articleId));
  }

  function getFilteredArticles(articleSelect, categoryValue, searchValue) {
    return getAllArticlesMeta(articleSelect).filter((meta) => {
      return (
        articleMatchesCategory(meta, categoryValue) &&
        articleMatchesSearch(meta, searchValue)
      );
    });
  }

  function syncCategoryWithSelection(row) {
    const { categorySelect, articleSelect } = getRowElements(row);
    if (!categorySelect || !articleSelect) return;

    const articleMeta = getArticleMeta(articleSelect);
    if (!articleMeta) return;

    const categoryLabel = String(articleMeta.categorie || "").trim();
    if (!categoryLabel) return;

    const hasOption = Array.from(categorySelect.options).some(
      (opt) => normalizeText(opt.value) === normalizeText(categoryLabel)
    );
    if (hasOption) {
      categorySelect.value = categoryLabel;
    }
  }

  function refreshArticleOptions(row) {
    const { categorySelect, articleSelect } = getRowElements(row);
    if (!articleSelect) return;

    const categoryValue = categorySelect ? String(categorySelect.value || "").trim() : "";
    const selectedValue = String(articleSelect.value || "").trim();
    const selectedInOtherRows = getSelectedArticleIds(row);
    const articles = getFilteredArticles(articleSelect, categoryValue, "");

    clearSelectOptions(articleSelect);
    articleSelect.appendChild(buildOption("", "Sélectionnez un article", !selectedValue));

    articles.forEach((meta) => {
      const labelBase = `${meta.nom} — ${meta.libelle_conditionnement || meta.resume_conditionnement || "—"}`;
      const isOut = Number(meta.stock_actuel_unites || 0) <= 0;
      const isAlreadySelectedElsewhere = selectedInOtherRows.has(String(meta.id));

      let label = labelBase;
      if (isOut) {
        label = `${labelBase} — Indisponible`;
      } else if (isAlreadySelectedElsewhere) {
        label = `${labelBase} — Déjà choisi`;
      }

      const option = buildOption(
        String(meta.id),
        label,
        selectedValue === String(meta.id)
      );

      option.dataset.baseLabel = labelBase;
      option.dataset.outOfStock = isOut ? "1" : "0";
      option.dataset.alreadySelected = isAlreadySelectedElsewhere ? "1" : "0";
      option.disabled = isOut || isAlreadySelectedElsewhere;

      articleSelect.appendChild(option);
    });

    const currentOption = articleSelect.options[articleSelect.selectedIndex];
    if (!currentOption || (currentOption.disabled && currentOption.value !== selectedValue) || !currentOption.value) {
      const selectedMeta = selectedValue ? getArticleMetaMap(articleSelect)[selectedValue] : null;
      if (
        selectedMeta &&
        articleMatchesCategory(selectedMeta, categoryValue) &&
        selectedMeta.est_disponible &&
        !selectedInOtherRows.has(String(selectedMeta.id))
      ) {
        articleSelect.value = selectedValue;
      } else {
        articleSelect.value = "";
      }
    }
  }

  function refreshAllArticleOptions() {
    const rows = Array.from(container.querySelectorAll(".formset-item"));
    rows.forEach((row) => {
      refreshArticleOptions(row);
    });
  }

  function hideSearchResults(resultsEl) {
    if (!resultsEl) return;
    resultsEl.innerHTML = "";
    resultsEl.classList.add("d-none");
  }

  function renderSearchResults(row) {
    const {
      categorySelect,
      articleSelect,
      articleSearchInput,
      articleSearchResults,
    } = getRowElements(row);

    if (!articleSelect || !articleSearchInput || !articleSearchResults) return;

    const categoryValue = categorySelect ? String(categorySelect.value || "").trim() : "";
    const searchValue = String(articleSearchInput.value || "").trim();

    if (!searchValue) {
      hideSearchResults(articleSearchResults);
      return;
    }

    const selectedInOtherRows = getSelectedArticleIds(row);
    const items = getFilteredArticles(articleSelect, categoryValue, searchValue);

    articleSearchResults.innerHTML = "";

    if (!items.length) {
      const empty = document.createElement("div");
      empty.className = "list-group-item text-muted small";
      empty.textContent =
        articleSelect.getAttribute("data-empty-search-message") || "Aucun article trouvé.";
      articleSearchResults.appendChild(empty);
      articleSearchResults.classList.remove("d-none");
      return;
    }

    items.slice(0, 20).forEach((meta) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "list-group-item list-group-item-action";

      const isOut = Number(meta.stock_actuel_unites || 0) <= 0;
      const isAlreadySelectedElsewhere = selectedInOtherRows.has(String(meta.id));

      if (isOut || isAlreadySelectedElsewhere) {
        btn.classList.add("disabled");
        btn.disabled = true;
      }

      let statusHtml = "";
      if (isOut) {
        statusHtml = `<div class="small text-danger">Indisponible</div>`;
      } else if (isAlreadySelectedElsewhere) {
        statusHtml = `<div class="small text-warning">Déjà choisi sur une autre ligne</div>`;
      } else {
        statusHtml = `<div class="small text-success">Stock actuel : ${meta.stock_actuel_unites || 0} unités</div>`;
      }

      btn.innerHTML = `
        <div class="fw-semibold">${meta.nom}</div>
        <div class="small text-muted">${meta.categorie || "Sans catégorie"} — ${meta.libelle_conditionnement || meta.resume_conditionnement || "—"}</div>
        ${statusHtml}
      `;

      if (!isOut && !isAlreadySelectedElsewhere) {
        btn.addEventListener("click", function () {
          articleSelect.value = String(meta.id);
          syncCategoryWithSelection(row);

          articleSearchInput.value = meta.nom;
          hideSearchResults(articleSearchResults);

          const { uniteSelect } = getRowElements(row);
          if (uniteSelect) {
            uniteSelect.setAttribute("data-selected", "Unité");
          }

          refreshAllArticleOptions();
          updateAllRowsState();
        });
      }

      articleSearchResults.appendChild(btn);
    });

    articleSearchResults.classList.remove("d-none");
  }

  function enterSearchMode(row) {
    const {
      articleSelectWrap,
      articleSearchWrap,
      articleSearchInput,
      articleSelect,
    } = getRowElements(row);

    if (!articleSelectWrap || !articleSearchWrap || !articleSearchInput || !articleSelect) return;

    articleSelectWrap.classList.add("d-none");
    articleSearchWrap.classList.remove("d-none");

    const articleMeta = getArticleMeta(articleSelect);
    articleSearchInput.value = articleMeta ? articleMeta.nom : "";
    articleSearchInput.focus();
    articleSearchInput.select();

    renderSearchResults(row);
  }

  function exitSearchMode(row) {
    const { articleSelectWrap, articleSearchWrap, articleSearchResults } = getRowElements(row);
    if (!articleSelectWrap || !articleSearchWrap) return;

    articleSearchWrap.classList.add("d-none");
    articleSelectWrap.classList.remove("d-none");
    hideSearchResults(articleSearchResults);
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

    if (isArticleAlreadyUsed(articleId, row)) {
      showQtyHelp(qtyHelp, "Cet article est déjà choisi sur une autre ligne.");
      refreshSubmitState();
      return false;
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

  function updateRowState(row) {
    const {
      articleSelect,
      articleSearchInput,
      articleSearchResults,
      uniteSelect,
      qtyInput,
      qtyHelp,
    } = getRowElements(row);

    if (!articleSelect || !uniteSelect || !qtyInput) return;

    const articleId = String(articleSelect.value || "").trim();
    const articleMeta = getArticleMeta(articleSelect);
    const selectedUnit =
      uniteSelect.getAttribute("data-selected") ||
      uniteSelect.dataset.defaultValue ||
      uniteSelect.value ||
      "Unité";

    fillUniteOptions(uniteSelect, articleMeta, selectedUnit);

    if (articleSearchInput) {
      articleSearchInput.value = articleMeta ? articleMeta.nom : "";
    }
    hideSearchResults(articleSearchResults);

    if (!articleMeta) {
      qtyInput.disabled = false;
      hideQtyHelp(qtyHelp);
      renderLineSummary(row);
      refreshSubmitState();
      return;
    }

    if (isArticleAlreadyUsed(articleId, row)) {
      qtyInput.value = "";
      qtyInput.disabled = true;
      showQtyHelp(qtyHelp, "Cet article est déjà choisi sur une autre ligne.");
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

  function updateAllRowsState() {
    const rows = Array.from(container.querySelectorAll(".formset-item"));
    rows.forEach((row) => updateRowState(row));
  }

  function attachRowEvents(row) {
    if (row.dataset.reqRowBound === "1") {
      updateRowState(row);
      return;
    }

    row.dataset.reqRowBound = "1";

    const {
      categorySelect,
      articleSelect,
      articleSearchInput,
      articleSearchResults,
      articleSearchButtons,
      uniteSelect,
      qtyInput,
      removeBtn,
    } = getRowElements(row);

    if (categorySelect) {
      categorySelect.addEventListener("change", function () {
        refreshArticleOptions(row);

        if (uniteSelect) {
          uniteSelect.setAttribute("data-selected", "Unité");
        }

        const currentMeta = getArticleMeta(articleSelect);
        if (!currentMeta && articleSearchInput) {
          articleSearchInput.value = "";
        }

        renderSearchResults(row);
        updateAllRowsState();
      });
    }

    if (articleSelect) {
      articleSelect.addEventListener("change", function () {
        syncCategoryWithSelection(row);

        if (uniteSelect) {
          uniteSelect.setAttribute("data-selected", "Unité");
        }

        refreshAllArticleOptions();
        updateAllRowsState();
      });

      refreshArticleOptions(row);
    }

    articleSearchButtons.forEach((btn) => {
      btn.addEventListener("click", function () {
        const { articleSearchWrap } = getRowElements(row);
        if (articleSearchWrap && articleSearchWrap.classList.contains("d-none")) {
          enterSearchMode(row);
        } else {
          exitSearchMode(row);
        }
      });
    });

    if (articleSearchInput) {
      articleSearchInput.addEventListener("input", function () {
        renderSearchResults(row);
      });

      articleSearchInput.addEventListener("focus", function () {
        renderSearchResults(row);
      });

      articleSearchInput.addEventListener("keydown", function (event) {
        if (event.key === "Escape") {
          event.preventDefault();
          exitSearchMode(row);
        }
      });
    }

    if (articleSearchResults) {
      articleSearchResults.addEventListener("mousedown", function (event) {
        event.preventDefault();
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

    const articleSearchWrap = clone.querySelector(".js-article-search-wrap");
    const articleSelectWrap = clone.querySelector(".js-article-select-wrap");
    const articleSearchInput = clone.querySelector(".js-article-search-input");
    const articleSearchResults = clone.querySelector(".js-article-search-results");

    if (articleSearchWrap) articleSearchWrap.classList.add("d-none");
    if (articleSelectWrap) articleSelectWrap.classList.remove("d-none");
    if (articleSearchInput) articleSearchInput.value = "";
    hideSearchResults(articleSearchResults);

    clone.dataset.reqRowBound = "0";
    return clone;
  }

  function addRow() {
    const row = createRowFromTemplate();
    if (!row) return;

    container.appendChild(row);
    refreshIndexes();
    attachRowEvents(row);
    refreshAllArticleOptions();
    updateAllRowsState();
    refreshSubmitState();
  }

  function removeRow(row) {
    const rows = Array.from(container.querySelectorAll(".formset-item"));

    if (rows.length <= 1) {
      const {
        categorySelect,
        articleSelect,
        articleSearchInput,
        articleSearchResults,
        articleSearchWrap,
        articleSelectWrap,
        uniteSelect,
        qtyInput,
        motifInput,
        deleteInput,
        qtyHelp,
      } = getRowElements(row);

      if (categorySelect) categorySelect.value = "";
      if (articleSelect) articleSelect.value = "";
      if (articleSearchInput) articleSearchInput.value = "";
      if (articleSearchWrap) articleSearchWrap.classList.add("d-none");
      if (articleSelectWrap) articleSelectWrap.classList.remove("d-none");
      hideSearchResults(articleSearchResults);

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

      refreshArticleOptions(row);
      hideQtyHelp(qtyHelp);
      refreshAllArticleOptions();
      updateAllRowsState();
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
      item.dataset.reqRowBound = "0";
      attachRowEvents(item);
    });

    refreshAllArticleOptions();
    updateAllRowsState();
    refreshSubmitState();
  }

  document.addEventListener("click", function (event) {
    const rows = Array.from(container.querySelectorAll(".formset-item"));
    rows.forEach((row) => {
      if (!row.contains(event.target)) {
        const { articleSearchResults } = getRowElements(row);
        hideSearchResults(articleSearchResults);
      }
    });
  });

  addBtn.addEventListener("click", addRow);

  Array.from(container.querySelectorAll(".formset-item")).forEach((row) => {
    attachRowEvents(row);
  });

  refreshAllArticleOptions();
  updateAllRowsState();

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