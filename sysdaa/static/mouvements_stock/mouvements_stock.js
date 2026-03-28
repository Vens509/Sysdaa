(function () {
  "use strict";

  function qs(selector, root) {
    return (root || document).querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.from((root || document).querySelectorAll(selector));
  }

  function normalizeText(value) {
    return String(value || "").trim();
  }

  function showElement(el) {
    if (!el) return;
    el.hidden = false;
    el.style.display = "";
  }

  function hideElement(el) {
    if (!el) return;
    el.hidden = true;
    el.style.display = "none";
  }

  function setReadonlyState(el, readonly) {
    if (!el) return;

    if (readonly) {
      el.setAttribute("readonly", "readonly");
      el.setAttribute("aria-readonly", "true");
      el.classList.add("bg-light");
    } else {
      el.removeAttribute("readonly");
      el.removeAttribute("aria-readonly");
      el.classList.remove("bg-light");
    }
  }

  function pluralize(word, n) {
    return Number(n) === 1 ? word : word + "s";
  }

  function getArticleOption(articleSelect) {
    if (!articleSelect) return null;
    return articleSelect.options[articleSelect.selectedIndex] || null;
  }

  function getArticleData(articleSelect) {
    const opt = getArticleOption(articleSelect);
    if (!opt || !opt.value) return null;

    return {
      unite: normalizeText(opt.dataset.articleUnite || "Unité") || "Unité",
      qpc: parseInt(opt.dataset.articleQpc || "1", 10) || 1,
      stockUnites: parseInt(opt.dataset.stockUnites || "0", 10) || 0,
      stockAffichage: normalizeText(opt.dataset.stockAffichage || "0 unité") || "0 unité",
      rupture: String(opt.dataset.stockRupture || "0") === "1",
    };
  }

  function buildEntryChoices(article) {
    const standards = [
      "Unité",
      "Boîte",
      "Paquet",
      "Carton",
      "Caisse",
      "Ramette",
      "Rame",
      "Douzaine",
      "Sac",
      "Bidon",
      "Bouteille",
      "Flacon",
      "Lot",
    ];

    const values = [...standards];

    if (article && article.unite && !values.includes(article.unite)) {
      values.push(article.unite);
    }

    values.push("AUTRE");
    return values;
  }

  function buildSortieChoices(article) {
    const values = ["Unité"];

    if (article && article.unite && article.unite !== "Unité") {
      values.push(article.unite);
    }

    return values;
  }

  function renderChoices(selectEl, values, currentValue, article, isSortie) {
    if (!selectEl) return;

    const previous = normalizeText(currentValue || selectEl.value);
    selectEl.innerHTML = "";

    const empty = document.createElement("option");
    empty.value = "";
    empty.textContent = "Sélectionnez un conditionnement";
    selectEl.appendChild(empty);

    values.forEach(function (value) {
      const opt = document.createElement("option");
      opt.value = value;
      opt.textContent = value === "AUTRE" ? "Autres" : value;
      selectEl.appendChild(opt);
    });

    const available = Array.from(selectEl.options).map(function (opt) {
      return opt.value;
    });

    if (previous && available.includes(previous)) {
      selectEl.value = previous;
      return;
    }

    if (isSortie) {
      if (article && article.unite && article.unite !== "Unité" && available.includes(article.unite)) {
        selectEl.value = article.unite;
        return;
      }

      if (available.includes("Unité")) {
        selectEl.value = "Unité";
        return;
      }
    }

    if (available.includes("Unité")) {
      selectEl.value = "Unité";
    }
  }

  function syncConditionnementUI(form) {
    const articleSelect = qs("#id_article", form);
    const conditionnementSelect = qs("#id_conditionnement_operation", form);
    const libreWrap = qs("#conditionnement-libre-wrap", form);
    const libreInput = qs("#id_conditionnement_operation_libre", form);
    const qpcInput = qs("#id_quantite_par_conditionnement_operation", form);

    if (!articleSelect || !conditionnementSelect || !qpcInput) return;

    const article = getArticleData(articleSelect);
    const isSortie = normalizeText(form.dataset.mouvementForm) === "sortie";

    const values = isSortie ? buildSortieChoices(article) : buildEntryChoices(article);
    renderChoices(conditionnementSelect, values, conditionnementSelect.value, article, isSortie);

    const selected = normalizeText(conditionnementSelect.value);

    if (!selected) {
      if (libreInput) libreInput.value = "";
      hideElement(libreWrap);
      qpcInput.value = "";
      setReadonlyState(qpcInput, false);
      return;
    }

    if (selected === "Unité") {
      if (libreInput) libreInput.value = "";
      hideElement(libreWrap);
      qpcInput.value = "1";
      setReadonlyState(qpcInput, true);
      return;
    }

    if (article && selected === article.unite) {
      if (libreInput) libreInput.value = "";
      hideElement(libreWrap);
      qpcInput.value = String(article.qpc || 1);
      setReadonlyState(qpcInput, true);
      return;
    }

    if (!isSortie && selected === "AUTRE") {
      showElement(libreWrap);
      qpcInput.value = normalizeText(qpcInput.value);
      setReadonlyState(qpcInput, false);
      return;
    }

    if (!isSortie) {
      if (libreInput) libreInput.value = "";
      hideElement(libreWrap);
      qpcInput.value = normalizeText(qpcInput.value);
      setReadonlyState(qpcInput, false);
    }
  }

  function syncMotifUI(form) {
    const motifSelect = qs("#id_motif_sortie_selection", form);
    const motifAutreWrap = qs("#motif-autre-wrap", form);
    const motifAutreInput = qs("#id_motif_sortie_autre", form);
    const motifHidden = qs("#id_motif_sortie", form);

    if (!motifSelect || !motifHidden) return;

    const selected = normalizeText(motifSelect.value);

    if (selected === "Autres") {
      showElement(motifAutreWrap);
      motifHidden.value = normalizeText(motifAutreInput ? motifAutreInput.value : "");
      return;
    }

    hideElement(motifAutreWrap);
    if (motifAutreInput) {
      motifAutreInput.value = "";
    }
    motifHidden.value = selected;
  }

  function syncSortieAvailability(form) {
    const articleSelect = qs("#id_article", form);
    const quantiteInput = qs("#id_quantite", form);
    const submitBtn = qs("#btn-enregistrer-sortie", form);
    const indisponibleInfo = qs("#article-indisponible-info", form);

    if (!articleSelect || !submitBtn) return;

    const article = getArticleData(articleSelect);
    const hasArticle = !!article;

    if (!hasArticle) {
      hideElement(indisponibleInfo);
      submitBtn.disabled = false;
      if (quantiteInput) quantiteInput.disabled = false;
      return;
    }

    if (article.rupture || article.stockUnites <= 0) {
      showElement(indisponibleInfo);
      submitBtn.disabled = true;
      if (quantiteInput) quantiteInput.disabled = true;
      return;
    }

    hideElement(indisponibleInfo);
    submitBtn.disabled = false;
    if (quantiteInput) quantiteInput.disabled = false;
  }

  function syncSummary(form) {
    const articleSelect = qs("#id_article", form);
    const conditionnementSelect = qs("#id_conditionnement_operation", form);
    const libreInput = qs("#id_conditionnement_operation_libre", form);
    const quantiteInput = qs("#id_quantite", form);
    const qpcInput = qs("#id_quantite_par_conditionnement_operation", form);

    const conditionnementInfo = qs("#article-conditionnement-info", form);
    const stockInfo = qs("#stock-actuel-info", form);
    const equivalentInfo = qs("#equivalent-unites-info", form);

    if (!articleSelect || !conditionnementSelect || !quantiteInput || !qpcInput) return;

    const article = getArticleData(articleSelect);
    const quantite = parseInt(quantiteInput.value || "0", 10) || 0;
    const qpc = parseInt(qpcInput.value || "0", 10) || 0;

    if (!article) {
      if (conditionnementInfo) {
        conditionnementInfo.textContent = "Conditionnement principal de l’article : —";
      }
      if (stockInfo) {
        stockInfo.textContent = "Stock actuel : —";
      }
      if (equivalentInfo) {
        equivalentInfo.textContent = "Équivalent réel : —";
      }
      return;
    }

    if (conditionnementInfo) {
      if (article.unite === "Unité" || article.qpc === 1) {
        conditionnementInfo.textContent = "Conditionnement principal de l’article : Unité";
      } else {
        conditionnementInfo.textContent =
          "Conditionnement principal de l’article : " +
          article.unite +
          " (" +
          article.qpc +
          " unités)";
      }
    }

    if (stockInfo) {
      stockInfo.textContent = "Stock actuel : " + article.stockAffichage;
    }

    let selected = normalizeText(conditionnementSelect.value);
    if (selected === "AUTRE" && libreInput) {
      selected = normalizeText(libreInput.value);
    }

    if (!selected || !quantite || !qpc) {
      if (equivalentInfo) {
        equivalentInfo.textContent = "Équivalent réel : —";
      }
      return;
    }

    const equivalent = quantite * qpc;
    const actionWord = normalizeText(form.dataset.mouvementForm) === "sortie" ? "sorti" : "ajouté";

    if (equivalentInfo) {
      equivalentInfo.textContent =
        "Équivalent réel " +
        actionWord +
        " : " +
        equivalent +
        " " +
        pluralize("unité", equivalent) +
        " (" +
        quantite +
        " " +
        pluralize(selected, quantite) +
        ")";
    }
  }

  function initForm(form) {
    const articleSelect = qs("#id_article", form);
    const conditionnementSelect = qs("#id_conditionnement_operation", form);
    const libreInput = qs("#id_conditionnement_operation_libre", form);
    const quantiteInput = qs("#id_quantite", form);
    const qpcInput = qs("#id_quantite_par_conditionnement_operation", form);
    const motifSelect = qs("#id_motif_sortie_selection", form);
    const motifAutreInput = qs("#id_motif_sortie_autre", form);

    if (!articleSelect || !conditionnementSelect || !quantiteInput || !qpcInput) {
      return;
    }

    function refreshAll() {
      syncConditionnementUI(form);
      syncMotifUI(form);
      syncSortieAvailability(form);
      syncSummary(form);
    }

    articleSelect.addEventListener("change", refreshAll);

    conditionnementSelect.addEventListener("change", function () {
      syncConditionnementUI(form);
      syncSummary(form);
    });

    quantiteInput.addEventListener("input", function () {
      syncSummary(form);
    });

    qpcInput.addEventListener("input", function () {
      syncSummary(form);
    });

    if (libreInput) {
      libreInput.addEventListener("input", function () {
        syncSummary(form);
      });
    }

    if (motifSelect) {
      motifSelect.addEventListener("change", function () {
        syncMotifUI(form);
      });
    }

    if (motifAutreInput) {
      motifAutreInput.addEventListener("input", function () {
        syncMotifUI(form);
      });
    }

    refreshAll();
  }

  document.addEventListener("DOMContentLoaded", function () {
    qsa('form[data-mouvement-form="entree"], form[data-mouvement-form="sortie"]').forEach(initForm);
  });
})();