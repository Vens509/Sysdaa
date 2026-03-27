(() => {
  const dailySeries = JSON.parse(
    document.getElementById("daily-series")?.textContent || "[]"
  );
  const monthlySeries = JSON.parse(
    document.getElementById("monthly-series")?.textContent || "[]"
  );
  const stockDonut = JSON.parse(
    document.getElementById("stock-donut")?.textContent ||
      '{"ok":0,"orange":0,"rouge":0}'
  );
  const reqPie = JSON.parse(
    document.getElementById("req-pie")?.textContent ||
      '{"labels":[],"data":[]}'
  );

  if (typeof Chart === "undefined") return;

  const COLORS = {
    ok: "#198754",
    orange: "#fd7e14",
    rouge: "#dc3545",
    bleu: "#194993",
    info: "#0d6efd",
    violet: "#6f42c1",
    teal: "#20c997",
    grille: "rgba(148, 163, 184, .18)"
  };

  Chart.defaults.font.family = "Inter, Segoe UI, Arial, sans-serif";
  Chart.defaults.color = "#425166";
  Chart.defaults.plugins.legend.labels.boxWidth = 10;

  function resetChart(canvas) {
    const existingChart = Chart.getChart(canvas);
    if (existingChart) {
      existingChart.destroy();
    }
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
        ctx.roundRect(x, y, boxWidth, boxHeight, 6);
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

  function baseOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      resizeDelay: 180,
      animation: {
        duration: 500
      },
      transitions: {
        resize: {
          animation: {
            duration: 0
          }
        }
      },
      plugins: {
        legend: {
          position: "bottom"
        },
        tooltip: {
          backgroundColor: "rgba(18, 32, 51, 0.95)",
          titleColor: "#fff",
          bodyColor: "#fff",
          padding: 12,
          cornerRadius: 10,
          callbacks: {
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
          }
        }
      }
    };
  }

  function renderStockDonut(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    resetChart(canvas);

    const ok = Number(stockDonut.ok || 0);
    const orange = Number(stockDonut.orange || 0);
    const rouge = Number(stockDonut.rouge || 0);

    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: ["OK", "Alerte Orange", "Alerte Rouge"],
        datasets: [
          {
            data: [ok, orange, rouge],
            backgroundColor: [COLORS.ok, COLORS.orange, COLORS.rouge],
            borderColor: ["#ffffff", "#ffffff", "#ffffff"],
            borderWidth: 3,
            hoverOffset: 8
          }
        ]
      },
      options: {
        ...baseOptions(),
        cutout: "68%",
        plugins: {
          ...baseOptions().plugins,
          legend: {
            display: false
          }
        }
      },
      plugins: [valuePercentLabelPlugin]
    });
  }

  function renderReqPie() {
    const canvas = document.getElementById("chartReqPie");
    if (!canvas) return;

    resetChart(canvas);

    const labels = reqPie.labels || [];
    const data = reqPie.data || [];

    new Chart(canvas, {
      type: "pie",
      data: {
        labels,
        datasets: [
          {
            data,
            backgroundColor: [
              "#194993",
              "#0d6efd",
              "#6f42c1",
              "#20c997",
              "#fd7e14",
              "#dc3545",
              "#94a3b8"
            ],
            borderColor: "#ffffff",
            borderWidth: 3
          }
        ]
      },
      options: {
        ...baseOptions()
      },
      plugins: [valuePercentLabelPlugin]
    });
  }

  function renderDailyLine() {
    const canvas = document.getElementById("chartDailyLine");
    if (!canvas) return;

    resetChart(canvas);

    const labels = dailySeries.map((item) => item.label);
    const entrees = dailySeries.map((item) => Number(item.entrees || 0));
    const sorties = dailySeries.map((item) => Number(item.sorties || 0));

    new Chart(canvas, {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Entrées",
            data: entrees,
            borderColor: COLORS.ok,
            backgroundColor: "rgba(25, 135, 84, 0.12)",
            tension: 0.35,
            fill: true,
            pointRadius: 3,
            pointHoverRadius: 5
          },
          {
            label: "Sorties",
            data: sorties,
            borderColor: COLORS.rouge,
            backgroundColor: "rgba(220, 53, 69, 0.10)",
            tension: 0.35,
            fill: true,
            pointRadius: 3,
            pointHoverRadius: 5
          }
        ]
      },
      options: {
        ...baseOptions(),
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
            grid: {
              color: COLORS.grille
            },
            ticks: {
              precision: 0
            }
          }
        }
      }
    });
  }

  function renderMonthlyBar() {
    const canvas = document.getElementById("chartMonthlyBar");
    if (!canvas) return;

    resetChart(canvas);

    const labels = monthlySeries.map((item) => item.label);
    const entrees = monthlySeries.map((item) => Number(item.entrees || 0));
    const sorties = monthlySeries.map((item) => Number(item.sorties || 0));

    new Chart(canvas, {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Entrées",
            data: entrees,
            backgroundColor: "rgba(25, 135, 84, 0.85)",
            borderRadius: 8,
            maxBarThickness: 34
          },
          {
            label: "Sorties",
            data: sorties,
            backgroundColor: "rgba(220, 53, 69, 0.85)",
            borderRadius: 8,
            maxBarThickness: 34
          }
        ]
      },
      options: {
        ...baseOptions(),
        scales: {
          x: {
            grid: {
              display: false
            }
          },
          y: {
            beginAtZero: true,
            grid: {
              color: COLORS.grille
            },
            ticks: {
              precision: 0
            }
          }
        }
      }
    });
  }

  renderStockDonut("chartStockDonut");
  renderReqPie();
  renderDailyLine();
  renderMonthlyBar();
})();