(() => {
  const labels = JSON.parse(
    document.getElementById("admin-daily-labels")?.textContent || "[]"
  );
  const values = JSON.parse(
    document.getElementById("admin-daily-values")?.textContent || "[]"
  );
  const auditActions = JSON.parse(
    document.getElementById("admin-audit-actions")?.textContent ||
      '{"labels":[],"values":[]}'
  );
  const auditLevels = JSON.parse(
    document.getElementById("admin-audit-levels")?.textContent ||
      '{"labels":[],"values":[]}'
  );

  if (typeof Chart === "undefined") return;

  const COLORS = {
    primary: "#194993",
    primarySoft: "rgba(25, 73, 147, 0.14)",
    success: "#198754",
    warning: "#fd7e14",
    danger: "#dc3545",
    info: "#0d6efd",
    violet: "#6f42c1",
    teal: "#20c997",
    slate: "#94a3b8",
    grid: "rgba(148, 163, 184, .18)"
  };

  Chart.defaults.font.family = "Inter, Segoe UI, Arial, sans-serif";
  Chart.defaults.color = "#425166";
  Chart.defaults.plugins.legend.labels.boxWidth = 10;

  const chartInstances = new Map();

  function destroyChart(canvas) {
    if (!canvas) return;

    const existing =
      chartInstances.get(canvas.id) || Chart.getChart(canvas);

    if (existing) {
      existing.destroy();
      chartInstances.delete(canvas.id);
    }
  }

  function saveChartInstance(canvas, instance) {
    if (!canvas || !instance) return;
    chartInstances.set(canvas.id, instance);
  }

  function debounce(fn, delay = 180) {
    let timer = null;
    return function debounced(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), delay);
    };
  }

  const valuePercentLabelPlugin = {
    id: "valuePercentLabelPlugin",
    afterDatasetsDraw(chart) {
      const chartType = chart.config.type;
      if (chartType !== "pie" && chartType !== "doughnut") return;

      const { ctx } = chart;
      const dataset = chart.data.datasets?.[0];
      if (!dataset || !Array.isArray(dataset.data)) return;

      const data = dataset.data.map((v) => Number(v) || 0);
      const total = data.reduce((sum, value) => sum + value, 0);
      if (!total) return;

      const meta = chart.getDatasetMeta(0);
      if (!meta || !meta.data) return;

      ctx.save();

      meta.data.forEach((element, index) => {
        const value = data[index];
        if (!value) return;

        const percent = Math.round((value / total) * 100);
        if (percent <= 0) return;

        const pos = element.tooltipPosition();
        const line1 = `${value}`;
        const line2 = `${percent}%`;

        const fontValue = "700 13px Inter, Segoe UI, Arial, sans-serif";
        const fontPercent = "600 11px Inter, Segoe UI, Arial, sans-serif";

        ctx.textAlign = "center";
        ctx.textBaseline = "middle";

        ctx.font = fontValue;
        const w1 = ctx.measureText(line1).width;

        ctx.font = fontPercent;
        const w2 = ctx.measureText(line2).width;

        const paddingX = 8;
        const paddingY = 6;
        const lineGap = 4;
        const boxWidth = Math.max(w1, w2) + paddingX * 2;
        const boxHeight = 16 + 12 + lineGap + paddingY * 2;

        const x = pos.x - boxWidth / 2;
        const y = pos.y - boxHeight / 2;

        ctx.fillStyle = "rgba(255,255,255,0.95)";
        ctx.beginPath();
        if (typeof ctx.roundRect === "function") {
          ctx.roundRect(x, y, boxWidth, boxHeight, 6);
        } else {
          ctx.rect(x, y, boxWidth, boxHeight);
        }
        ctx.fill();

        ctx.fillStyle = "#16324f";
        ctx.font = fontValue;
        ctx.fillText(line1, pos.x, y + paddingY + 8);

        ctx.font = fontPercent;
        ctx.fillText(line2, pos.x, y + paddingY + 8 + 16 + lineGap);
      });

      ctx.restore();
    }
  };

  function getCommonPlugins() {
    return {
      legend: {
        position: "bottom"
      },
      tooltip: {
        backgroundColor: "rgba(18, 32, 51, 0.95)",
        titleColor: "#fff",
        bodyColor: "#fff",
        padding: 12,
        cornerRadius: 10
      }
    };
  }

  function getPieTooltipCallbacks() {
    return {
      label(context) {
        const dataset = context.dataset?.data || [];
        const total = dataset.reduce(
          (sum, value) => sum + (Number(value) || 0),
          0
        );
        const value = Number(context.raw) || 0;
        const percent = total ? Math.round((value / total) * 100) : 0;
        return `${context.label || ""} : ${value} (${percent}%)`;
      }
    };
  }

  function lineOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 200,
      animation: false,
      normalized: true,
      plugins: getCommonPlugins(),
      interaction: {
        mode: "index",
        intersect: false
      },
      scales: {
        x: {
          grid: {
            display: false
          }
        },
        y: {
          beginAtZero: true,
          ticks: {
            precision: 0
          },
          grid: {
            color: COLORS.grid
          }
        }
      }
    };
  }

  function roundChartOptions(cutoutValue = undefined) {
    const options = {
      responsive: true,
      maintainAspectRatio: true,
      aspectRatio: 1,
      resizeDelay: 200,
      animation: false,
      normalized: true,
      layout: {
        padding: 8
      },
      plugins: {
        ...getCommonPlugins(),
        tooltip: {
          ...getCommonPlugins().tooltip,
          callbacks: getPieTooltipCallbacks()
        }
      }
    };

    if (cutoutValue !== undefined) {
      options.cutout = cutoutValue;
    }

    return options;
  }

  function renderUsersDaily() {
    const canvas = document.getElementById("chartAdminUsersDaily");
    if (!canvas) return;

    destroyChart(canvas);

    const chart = new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Créations utilisateurs",
            data: values,
            borderColor: COLORS.primary,
            backgroundColor: COLORS.primarySoft,
            fill: true,
            tension: 0.35,
            pointRadius: 3,
            pointHoverRadius: 5
          }
        ]
      },
      options: lineOptions()
    });

    saveChartInstance(canvas, chart);
  }

  function renderAuditLevels() {
    const canvas = document.getElementById("chartAuditLevels");
    if (!canvas) return;

    destroyChart(canvas);

    const chart = new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: auditLevels.labels || [],
        datasets: [
          {
            data: auditLevels.values || [],
            backgroundColor: [
              COLORS.primary,
              COLORS.warning,
              COLORS.danger,
              COLORS.info,
              COLORS.slate
            ],
            borderColor: "#ffffff",
            borderWidth: 3,
            hoverOffset: 8
          }
        ]
      },
      options: roundChartOptions("68%"),
      plugins: [valuePercentLabelPlugin]
    });

    saveChartInstance(canvas, chart);
  }

  function renderAuditActions() {
    const canvas = document.getElementById("chartAuditActions");
    if (!canvas) return;

    destroyChart(canvas);

    const chart = new Chart(canvas, {
      type: "pie",
      data: {
        labels: auditActions.labels || [],
        datasets: [
          {
            data: auditActions.values || [],
            backgroundColor: [
              COLORS.primary,
              COLORS.info,
              COLORS.violet,
              COLORS.teal,
              COLORS.warning,
              COLORS.danger,
              COLORS.slate
            ],
            borderColor: "#ffffff",
            borderWidth: 3
          }
        ]
      },
      options: roundChartOptions(),
      plugins: [valuePercentLabelPlugin]
    });

    saveChartInstance(canvas, chart);
  }

  function renderAllCharts() {
    renderUsersDaily();
    renderAuditLevels();
    renderAuditActions();
  }

  const rerenderOnResize = debounce(() => {
    renderAllCharts();
  }, 220);

  window.addEventListener("resize", rerenderOnResize);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) {
      rerenderOnResize();
    }
  });

  renderAllCharts();
})();