(function () {
  "use strict";

  function qs(selector, root) {
    return (root || document).querySelector(selector);
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
    } else {
      el.removeAttribute("readonly");
      el.removeAttribute("aria-readonly");
    }
  }

  function normalizeText(value) {
    return String(value || "").trim();
  }

  function buildKnownUnits(selectEl) {
    if (!selectEl) return new Set();
    const known = new Set();

    Array.from(selectEl.options).forEach(function (option) {
      const value = normalizeText(option.value);
      if (value && value !== "Autres") {
        known.add(value.toLowerCase());
      }
    });

    return known;
  }

  function ensureCustomOption(selectEl, value) {
    if (!selectEl) return;
    const normalized = normalizeText(value);
    if (!normalized || normalized.toLowerCase() === "autres") return;

    const exists = Array.from(selectEl.options).some(function (option) {
      return normalizeText(option.value).toLowerCase() === normalized.toLowerCase();
    });

    if (!exists) {
      const autresOption = Array.from(selectEl.options).find(function (option) {
        return normalizeText(option.value) === "Autres";
      });

      const newOption = document.createElement("option");
      newOption.value = normalized;
      newOption.textContent = normalized;

      if (autresOption && autresOption.parentNode === selectEl) {
        selectEl.insertBefore(newOption, autresOption);
      } else {
        selectEl.appendChild(newOption);
      }
    }
  }

  function syncUnitUI() {
    const picker = qs("[data-unite-picker]");
    if (!picker) return;

    const selectWrap = qs("[data-unite-select-wrap]", picker);
    const customWrap = qs("[data-unite-custom-wrap]", picker);
    const selectUi = qs("[data-unite-select-ui]", picker);
    const customUi = qs("[data-unite-custom-ui]", picker);
    const realInput =
      qs('input[name="unite"], textarea[name="unite"], select[name="unite"]', picker) ||
      qs("#id_unite");

    if (!selectUi || !customUi || !realInput) return;

    const currentRealValue = normalizeText(realInput.value);
    const knownUnits = buildKnownUnits(selectUi);
    const isKnownValue = currentRealValue && knownUnits.has(currentRealValue.toLowerCase());

    if (!currentRealValue) {
      selectUi.value = "";
      customUi.value = "";
      hideElement(customWrap);
      showElement(selectWrap);
      return;
    }

    if (isKnownValue) {
      ensureCustomOption(selectUi, currentRealValue);
      selectUi.value = currentRealValue;
      customUi.value = "";
      hideElement(customWrap);
      showElement(selectWrap);
    } else {
      selectUi.value = "Autres";
      customUi.value = currentRealValue;
      showElement(customWrap);
      showElement(selectWrap);
    }
  }

  function bindUnitPicker() {
    const picker = qs("[data-unite-picker]");
    if (!picker) return;

    const selectWrap = qs("[data-unite-select-wrap]", picker);
    const customWrap = qs("[data-unite-custom-wrap]", picker);
    const selectUi = qs("[data-unite-select-ui]", picker);
    const customUi = qs("[data-unite-custom-ui]", picker);
    const realInput =
      qs('input[name="unite"], textarea[name="unite"], select[name="unite"]', picker) ||
      qs("#id_unite");

    if (!selectUi || !customUi || !realInput) return;

    const isLocked = realInput.disabled || realInput.readOnly;

    function writeToRealInput(value) {
      realInput.value = normalizeText(value);
      realInput.dispatchEvent(new Event("input", { bubbles: true }));
      realInput.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function applyMode() {
      const selected = normalizeText(selectUi.value);

      if (selected === "Autres") {
        showElement(customWrap);
        setReadonlyState(customUi, false);
        customUi.disabled = false;

        const customValue = normalizeText(customUi.value);
        writeToRealInput(customValue);

        setTimeout(function () {
          if (!isLocked) customUi.focus();
        }, 0);
      } else {
        hideElement(customWrap);
        customUi.value = "";
        setReadonlyState(customUi, true);
        customUi.disabled = false;
        writeToRealInput(selected);
      }
    }

    if (isLocked) {
      selectUi.disabled = true;
      customUi.disabled = true;
      setReadonlyState(customUi, true);
    }

    syncUnitUI();

    if (!isLocked) {
      selectUi.addEventListener("change", applyMode);

      customUi.addEventListener("input", function () {
        if (normalizeText(selectUi.value) !== "Autres") return;
        writeToRealInput(customUi.value);
      });

      customUi.addEventListener("blur", function () {
        const value = normalizeText(customUi.value);
        if (!value) return;
        ensureCustomOption(selectUi, value);
      });

      const form = qs("#articleForm");
      if (form) {
        form.addEventListener("submit", function () {
          const selected = normalizeText(selectUi.value);

          if (selected === "Autres") {
            const customValue = normalizeText(customUi.value);
            writeToRealInput(customValue);
            ensureCustomOption(selectUi, customValue);
          } else {
            writeToRealInput(selected);
          }
        });
      }
    }
  }

  function bindCategoryToggle() {
    const toggleBtn = qs("[data-toggle-category-create]");
    const selectWrap = qs("[data-category-select-wrap]");
    const inputWrap = qs("[data-category-input-wrap]");
    const categorySelect = qs('select[name="categorie"]');
    const categoryInput = qs('input[name="categorie_libre"]');

    if (!toggleBtn || !selectWrap || !inputWrap || !categorySelect || !categoryInput) return;

    function syncCategoryMode(forceInput) {
      const hasFreeValue = normalizeText(categoryInput.value) !== "";
      const useInput = forceInput === true || hasFreeValue;

      if (useInput) {
        hideElement(selectWrap);
        showElement(inputWrap);
        categorySelect.value = "";
        setTimeout(function () {
          categoryInput.focus();
        }, 0);
      } else {
        showElement(selectWrap);
        hideElement(inputWrap);
      }
    }

    toggleBtn.addEventListener("click", function () {
      const isHidden = inputWrap.hidden || inputWrap.style.display === "none";
      syncCategoryMode(isHidden);
    });

    categoryInput.addEventListener("input", function () {
      if (normalizeText(categoryInput.value) === "") {
        return;
      }
      hideElement(selectWrap);
      showElement(inputWrap);
      categorySelect.value = "";
    });

    syncCategoryMode(false);
  }

  function bindFournisseursToggle() {
    const toggleBtn = qs("[data-toggle-fournisseurs-create]");
    const inputWrap = qs("[data-fournisseurs-input-wrap]");
    const textarea = qs('textarea[name="fournisseurs_libres"]');

    if (!toggleBtn || !inputWrap || !textarea) return;

    function syncMode(forceOpen) {
      const hasValue = normalizeText(textarea.value) !== "";
      const open = forceOpen === true || hasValue;

      if (open) {
        showElement(inputWrap);
        setTimeout(function () {
          textarea.focus();
        }, 0);
      } else {
        hideElement(inputWrap);
      }
    }

    toggleBtn.addEventListener("click", function () {
      const isHidden = inputWrap.hidden || inputWrap.style.display === "none";
      syncMode(isHidden);
    });

    syncMode(false);
  }

  function bindConditionnementHints() {
    const uniteInput = qs('input[name="unite"]');
    const uniteUi = qs("[data-unite-select-ui]");
    const qpcInput = qs('input[name="quantite_par_conditionnement"]');
    const helpText = document.getElementById("qpcHelpText");

    if (!qpcInput) return;

    const qpcFieldContainer = qpcInput.closest(".col-md-6") || qpcInput.parentElement;
    const qpcErrorBlock = qpcFieldContainer
      ? qpcFieldContainer.querySelector(".text-danger.small.mt-1")
      : null;

    const defaultPlaceholder =
      qpcInput.getAttribute("placeholder") ||
      "Ex. 12 pour une douzaine, 20 pour une boîte de 20";

    function getCurrentUnit() {
      const real = uniteInput ? normalizeText(uniteInput.value) : "";
      const ui = uniteUi ? normalizeText(uniteUi.value) : "";
      if (ui && ui !== "Autres") return ui;
      return real;
    }

    function getForcedQuantity(unitRaw) {
      const unit = normalizeText(unitRaw).toLowerCase();
      if (!unit) return null;

      if (unit === "unité" || unit === "unite") return 1;
      if (unit === "bidon") return 1;
      if (unit === "bouteille") return 1;
      if (unit === "douzaine") return 12;

      return null;
    }

    function manageHelpText(unitRaw) {
      if (!helpText) return;

      const unit = normalizeText(unitRaw).toLowerCase();
      const hideFor = ["unité", "unite", "bouteille", "bidon", "douzaine"];

      if (hideFor.includes(unit)) {
        helpText.style.display = "none";
      } else {
        helpText.style.display = "";
      }
    }

    function manageQpcErrorVisibility(unitRaw, forcedQuantity) {
      if (!qpcErrorBlock) return;

      const unit = normalizeText(unitRaw).toLowerCase();
      const lockedUnits = ["unité", "unite", "bouteille", "bidon", "douzaine"];

      if (!lockedUnits.includes(unit)) {
        qpcErrorBlock.style.display = "";
        return;
      }

      const currentValue = parseInt(qpcInput.value || "0", 10);
      if (!Number.isNaN(currentValue) && currentValue === forcedQuantity) {
        qpcErrorBlock.style.display = "none";
      } else {
        qpcErrorBlock.style.display = "";
      }
    }

    function lockQpc(value, helpPlaceholder) {
      qpcInput.value = String(value);
      qpcInput.setAttribute("min", String(value));
      qpcInput.setAttribute("max", String(value));
      qpcInput.setAttribute("step", "1");
      setReadonlyState(qpcInput, true);
      qpcInput.classList.add("bg-light");
      qpcInput.setAttribute("tabindex", "-1");
      qpcInput.setAttribute("data-auto-locked", "1");
      qpcInput.setAttribute("data-locked-value", String(value));
      qpcInput.setAttribute("placeholder", helpPlaceholder);
    }

    function unlockQpc() {
      setReadonlyState(qpcInput, false);
      qpcInput.classList.remove("bg-light");
      qpcInput.removeAttribute("tabindex");
      qpcInput.removeAttribute("data-auto-locked");
      qpcInput.removeAttribute("data-locked-value");
      qpcInput.setAttribute("min", "1");
      qpcInput.removeAttribute("max");
      qpcInput.setAttribute("step", "1");
      qpcInput.setAttribute("placeholder", defaultPlaceholder);
    }

    function applyHintLogic() {
      const unit = getCurrentUnit();
      const forcedQuantity = getForcedQuantity(unit);

      manageHelpText(unit);

      if (forcedQuantity === null) {
        unlockQpc();
        manageQpcErrorVisibility(unit, null);
        return;
      }

      if (forcedQuantity === 1) {
        lockQpc(1, "Fixé automatiquement à 1 pour ce conditionnement");
        manageQpcErrorVisibility(unit, 1);
        return;
      }

      if (forcedQuantity === 12) {
        lockQpc(12, "Fixé automatiquement à 12 pour Douzaine");
        manageQpcErrorVisibility(unit, 12);
      }
    }

    if (uniteUi) {
      uniteUi.addEventListener("change", applyHintLogic);
    }

    if (uniteInput) {
      uniteInput.addEventListener("input", applyHintLogic);
      uniteInput.addEventListener("change", applyHintLogic);
    }

    qpcInput.addEventListener("input", function () {
      if (!qpcInput.hasAttribute("data-auto-locked")) return;
      const lockedValue = qpcInput.getAttribute("data-locked-value");
      if (lockedValue) {
        qpcInput.value = lockedValue;
      }
    });

    qpcInput.addEventListener("change", function () {
      if (!qpcInput.hasAttribute("data-auto-locked")) return;
      const lockedValue = qpcInput.getAttribute("data-locked-value");
      if (lockedValue) {
        qpcInput.value = lockedValue;
      }
      applyHintLogic();
    });

    const form = qs("#articleForm");
    if (form) {
      form.addEventListener("submit", function () {
        const forcedQuantity = getForcedQuantity(getCurrentUnit());
        if (forcedQuantity !== null) {
          qpcInput.value = String(forcedQuantity);
        }
      });
    }

    applyHintLogic();
  }

  function init() {
    bindCategoryToggle();
    bindFournisseursToggle();
    bindUnitPicker();
    bindConditionnementHints();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();