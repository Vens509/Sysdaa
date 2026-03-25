document.addEventListener("DOMContentLoaded", function () {
  const toggleBtn = document.getElementById("toggleDeleteModeBtn");
  const cancelBtn = document.getElementById("cancelDeleteModeBtn");
  const selectAllBtn = document.getElementById("selectAllNotificationsBtn");
  const unselectAllBtn = document.getElementById("unselectAllNotificationsBtn");
  const toolbar = document.getElementById("deleteModeToolbar");
  const form = document.getElementById("deleteNotificationsForm");
  const selectBoxes = document.querySelectorAll(".notif-select-box");
  const checkboxes = document.querySelectorAll(".notif-checkbox");
  const notifActions = document.querySelectorAll(".notif-actions");
  const notifItems = document.querySelectorAll(".notif-item");

  const topbarNotifBtn = document.getElementById("topbarNotifBtn");
  const topbarNotifBadge = document.getElementById("topbarNotifBadge");
  const topbarNotifList = document.getElementById("topbarNotifList");
  const topbarNotifEmpty = document.getElementById("topbarNotifEmpty");
  const topbarNotifLiveUrl = topbarNotifBtn
    ? topbarNotifBtn.getAttribute("data-live-url")
    : "";

  let deleteMode = false;
  let liveRefreshTimer = null;

  function setDeleteMode(enabled) {
    deleteMode = enabled;

    if (toolbar) {
      toolbar.classList.toggle("d-none", !enabled);
    }

    selectBoxes.forEach((box) => {
      box.classList.toggle("d-none", !enabled);
    });

    notifActions.forEach((box) => {
      box.classList.toggle("d-none", enabled);
    });

    notifItems.forEach((item) => {
      item.classList.toggle("notif-item--clickable", !enabled);
    });

    if (toggleBtn) {
      if (enabled) {
        toggleBtn.classList.add("d-none");
      } else {
        toggleBtn.classList.remove("d-none");
      }
    }

    if (!enabled) {
      checkboxes.forEach((cb) => {
        cb.checked = false;
      });
    }
  }

  function bindNotificationsListPage() {
    if (!form) {
      return;
    }

    if (toggleBtn) {
      toggleBtn.addEventListener("click", function () {
        setDeleteMode(true);
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        setDeleteMode(false);
      });
    }

    if (selectAllBtn) {
      selectAllBtn.addEventListener("click", function () {
        checkboxes.forEach((cb) => {
          cb.checked = true;
        });
      });
    }

    if (unselectAllBtn) {
      unselectAllBtn.addEventListener("click", function () {
        checkboxes.forEach((cb) => {
          cb.checked = false;
        });
      });
    }

    form.addEventListener("submit", function (event) {
      if (!deleteMode) {
        event.preventDefault();
        return;
      }

      const checked = Array.from(checkboxes).filter((cb) => cb.checked);

      if (checked.length === 0) {
        event.preventDefault();
        alert("Veuillez cocher au moins une notification à supprimer.");
      }
    });

    notifItems.forEach((item) => {
      item.addEventListener("click", function (event) {
        if (deleteMode) {
          return;
        }

        const clickedInteractive = event.target.closest(
          "a, button, input, label, select, textarea"
        );

        if (clickedInteractive) {
          return;
        }

        const openUrl = item.dataset.openUrl;
        if (openUrl) {
          window.location.href = openUrl;
        }
      });
    });

    setDeleteMode(false);
  }

  function renderTopbarBadge(count) {
    if (!topbarNotifBadge) {
      return;
    }

    const total = Number(count || 0);

    if (total > 0) {
      topbarNotifBadge.textContent = total > 99 ? "99+" : String(total);
      topbarNotifBadge.classList.remove("d-none");
    } else {
      topbarNotifBadge.textContent = "0";
      topbarNotifBadge.classList.add("d-none");
    }
  }

  function buildTopbarNotificationItem(notification) {
    const link = document.createElement("a");
    link.href = notification.url || "#";
    link.className = "list-group-item list-group-item-action border-0 px-3 py-3";

    if (!notification.lu) {
      link.classList.add("fw-semibold");
      link.classList.add("bg-light");
    }

    const title = document.createElement("div");
    title.className = "small fw-bold text-dark mb-1";
    title.textContent = notification.titre || "Notification";

    const message = document.createElement("div");
    message.className = "small text-muted mb-1";
    message.textContent = notification.message || "";

    const date = document.createElement("div");
    date.className = "small text-secondary";
    date.textContent = notification.date || "";

    link.appendChild(title);
    link.appendChild(message);
    link.appendChild(date);

    return link;
  }

  function renderTopbarNotifications(items) {
    if (!topbarNotifList || !topbarNotifEmpty) {
      return;
    }

    topbarNotifList.innerHTML = "";

    if (!items || !items.length) {
      topbarNotifEmpty.classList.remove("d-none");
      return;
    }

    topbarNotifEmpty.classList.add("d-none");

    items.forEach((item) => {
      topbarNotifList.appendChild(buildTopbarNotificationItem(item));
    });
  }

  async function refreshTopbarNotifications() {
    if (!topbarNotifLiveUrl) {
      return;
    }

    try {
      const response = await fetch(topbarNotifLiveUrl, {
        method: "GET",
        headers: {
          "X-Requested-With": "XMLHttpRequest",
          Accept: "application/json",
        },
        credentials: "same-origin",
        cache: "no-store",
      });

      if (!response.ok) {
        return;
      }

      const payload = await response.json();

      renderTopbarBadge(payload.nb_non_lues || 0);
      renderTopbarNotifications(payload.notifications || []);
    } catch (error) {
      console.error("Erreur lors de l'actualisation des notifications live.", error);
    }
  }

  function initTopbarNotificationsLive() {
    if (!topbarNotifBtn || !topbarNotifList || !topbarNotifLiveUrl) {
      return;
    }

    refreshTopbarNotifications();

    if (liveRefreshTimer) {
      window.clearInterval(liveRefreshTimer);
    }

    liveRefreshTimer = window.setInterval(function () {
      refreshTopbarNotifications();
    }, 5000);
  }

  bindNotificationsListPage();
  initTopbarNotificationsLive();
});