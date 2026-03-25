(() => {
  const labels = JSON.parse(
    document.getElementById("secretaire-monthly-labels")?.textContent || "[]"
  );
  const values = JSON.parse(
    document.getElementById("secretaire-monthly-values")?.textContent || "[]"
  );

  if (typeof Chart === "undefined") return;

  function resetChart(canvas) {
    const existingChart = Chart.getChart(canvas);
    if (existingChart) {
      existingChart.destroy();
    }
  }

  const canvas = document.getElementById("chartReqByMonth");
  if (!canvas) return;

  resetChart(canvas);

  new Chart(canvas, {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Réquisitions",
          data: values,
          backgroundColor: "#194993",
          borderRadius: 8,
          maxBarThickness: 42
        }
      ]
    },
    options: {
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
          cornerRadius: 10
        }
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
            color: "rgba(148, 163, 184, .18)"
          }
        }
      }
    }
  });
})();