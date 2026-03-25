/* sysdaa/static/sysdaa/sidebar.js */

document.addEventListener("DOMContentLoaded", () => {
  const sidebar = document.querySelector(".sys-sidebar");
  const pinBtn = document.getElementById("sidebarPinBtn");

  if (!sidebar || typeof bootstrap === "undefined" || !bootstrap.Collapse) {
    return;
  }

  const desktopQuery = window.matchMedia("(min-width: 992px)");
  const PIN_KEY = "sysdaa_sidebar_pinned";

  function getOpenCollapses() {
    return Array.from(sidebar.querySelectorAll(".collapse.show"));
  }

  function getToggleForCollapse(collapseEl) {
    const collapseId = collapseEl.getAttribute("id");
    if (!collapseId) return null;

    return sidebar.querySelector(
      `[data-bs-target="#${collapseId}"], [href="#${collapseId}"]`
    );
  }

  function setToggleExpanded(toggleEl, expanded) {
    if (!toggleEl) return;
    toggleEl.setAttribute("aria-expanded", expanded ? "true" : "false");
  }

  function hideCollapse(collapseEl) {
    const instance =
      bootstrap.Collapse.getInstance(collapseEl) ||
      new bootstrap.Collapse(collapseEl, { toggle: false });

    instance.hide();

    const toggle = getToggleForCollapse(collapseEl);
    setToggleExpanded(toggle, false);
  }

  function hideAllOpenCollapses() {
    getOpenCollapses().forEach(hideCollapse);
  }

  function syncTogglesState() {
    sidebar.querySelectorAll(".collapse").forEach((collapseEl) => {
      const toggle = getToggleForCollapse(collapseEl);
      if (!toggle) return;

      const isExpanded = collapseEl.classList.contains("show");
      setToggleExpanded(toggle, isExpanded);
    });
  }

  function isPinned() {
    return sidebar.classList.contains("is-pinned");
  }

  function updatePinButtonUI(pinned) {
    if (!pinBtn) return;

    pinBtn.setAttribute("aria-pressed", pinned ? "true" : "false");
    pinBtn.setAttribute(
      "title",
      pinned ? "Désépingler le menu" : "Épingler le menu"
    );
    pinBtn.setAttribute(
      "aria-label",
      pinned ? "Désépingler le menu latéral" : "Épingler le menu latéral"
    );
  }

  function applyPinnedState(pinned, options = {}) {
    const { persist = true } = options;

    const canPin = desktopQuery.matches;
    const finalPinned = canPin ? pinned : false;

    sidebar.classList.toggle("is-pinned", finalPinned);
    updatePinButtonUI(finalPinned);

    if (persist) {
      if (finalPinned) {
        localStorage.setItem(PIN_KEY, "1");
      } else {
        localStorage.removeItem(PIN_KEY);
      }
    }

    if (!finalPinned) {
      hideAllOpenCollapses();
    }
  }

  function restorePinnedState() {
    const saved = localStorage.getItem(PIN_KEY) === "1";

    if (!desktopQuery.matches) {
      applyPinnedState(false, { persist: false });
      return;
    }

    applyPinnedState(saved, { persist: false });
  }

  function handleViewportChange() {
    if (!desktopQuery.matches) {
      hideAllOpenCollapses();
      applyPinnedState(false, { persist: false });
    } else {
      restorePinnedState();
    }
  }

  if (pinBtn) {
    pinBtn.addEventListener("click", () => {
      if (!desktopQuery.matches) return;
      applyPinnedState(!isPinned());
    });
  }

  sidebar.addEventListener("mouseleave", () => {
    if (!desktopQuery.matches) return;
    if (isPinned()) return;
    hideAllOpenCollapses();
  });

  sidebar.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;

    if (isPinned()) {
      applyPinnedState(false);
    } else {
      hideAllOpenCollapses();
    }
  });

  desktopQuery.addEventListener("change", handleViewportChange);

  sidebar.querySelectorAll(".collapse").forEach((collapseEl) => {
    collapseEl.addEventListener("shown.bs.collapse", () => {
      const toggle = getToggleForCollapse(collapseEl);
      setToggleExpanded(toggle, true);
    });

    collapseEl.addEventListener("hidden.bs.collapse", () => {
      const toggle = getToggleForCollapse(collapseEl);
      setToggleExpanded(toggle, false);
    });
  });

  handleViewportChange();
  syncTogglesState();
});