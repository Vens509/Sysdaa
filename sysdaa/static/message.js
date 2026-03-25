(function () {
  "use strict";

  const AUTO_DISMISS_DELAY = 5000;
  const EXIT_ANIMATION_MS = 260;
  const SELECTOR = ".sys-flash.alert";

  function ensureProgressBar(flash) {
    let bar = flash.querySelector(".sys-flash__progress");
    if (bar) return bar;

    bar = document.createElement("div");
    bar.className = "sys-flash__progress";
    flash.appendChild(bar);
    return bar;
  }

  function setProgress(bar, ratio) {
    const safeRatio = Math.max(0, Math.min(1, ratio));
    bar.style.transform = `scaleX(${safeRatio})`;
  }

  function closeFlash(flash) {
    if (!flash || flash.dataset.closing === "1") return;

    flash.dataset.closing = "1";
    flash.classList.remove("show");
    flash.classList.add("sys-flash--closing");

    window.setTimeout(() => {
      if (flash && flash.parentNode) {
        flash.remove();
      }
    }, EXIT_ANIMATION_MS);
  }

  function initFlash(flash) {
    if (!flash || flash.dataset.autodismissReady === "1") return;
    flash.dataset.autodismissReady = "1";

    const bar = ensureProgressBar(flash);

    let remaining = AUTO_DISMISS_DELAY;
    let startedAt = null;
    let timerId = null;
    let rafId = null;
    let paused = false;
    let closed = false;

    function cleanupTimers() {
      if (timerId) {
        clearTimeout(timerId);
        timerId = null;
      }
      if (rafId) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
    }

    function tick() {
      if (paused || closed) return;

      const elapsed = Date.now() - startedAt;
      const ratio = 1 - elapsed / remaining;
      setProgress(bar, ratio);

      if (elapsed < remaining) {
        rafId = requestAnimationFrame(tick);
      }
    }

    function startTimer(duration) {
      cleanupTimers();
      startedAt = Date.now();
      remaining = duration;
      setProgress(bar, 1);

      timerId = window.setTimeout(() => {
        closed = true;
        closeFlash(flash);
      }, duration);

      rafId = requestAnimationFrame(tick);
    }

    function pauseTimer() {
      if (paused || closed) return;
      paused = true;

      const elapsed = Date.now() - startedAt;
      remaining = Math.max(0, remaining - elapsed);

      cleanupTimers();
      setProgress(bar, remaining / AUTO_DISMISS_DELAY);
    }

    function resumeTimer() {
      if (!paused || closed) return;
      paused = false;

      if (remaining <= 0) {
        closed = true;
        closeFlash(flash);
        return;
      }

      startTimer(remaining);
    }

    const closeBtn = flash.querySelector('[data-bs-dismiss="alert"], .btn-close, .sys-flash__close');
    if (closeBtn) {
      closeBtn.addEventListener("click", function () {
        closed = true;
        cleanupTimers();
        closeFlash(flash);
      });
    }

    flash.addEventListener("mouseenter", pauseTimer);
    flash.addEventListener("mouseleave", resumeTimer);

    flash.addEventListener("focusin", pauseTimer);
    flash.addEventListener("focusout", function () {
      const active = document.activeElement;
      if (!flash.contains(active)) {
        resumeTimer();
      }
    });

    startTimer(AUTO_DISMISS_DELAY);
  }

  function initAllFlashes(root) {
    const scope = root || document;
    const flashes = scope.querySelectorAll(SELECTOR);
    flashes.forEach(initFlash);
  }

  function observeNewFlashes() {
    const observer = new MutationObserver((mutations) => {
      for (const mutation of mutations) {
        mutation.addedNodes.forEach((node) => {
          if (!(node instanceof HTMLElement)) return;

          if (node.matches && node.matches(SELECTOR)) {
            initFlash(node);
          } else {
            initAllFlashes(node);
          }
        });
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAllFlashes(document);
    observeNewFlashes();
  });
})();