
const $ = (id) => document.getElementById(id);

let monthlyChart = null;
let categoryChart = null;
let productChart = null;
let filtersLoaded = false;
let searchTimer = null;
let requestNumber = 0;

function money(value) {
    return "₹" + Number(value || 0).toLocaleString("en-IN", {
        maximumFractionDigits: 2
    });
}

function showMessage(message, isError = false) {
    $("message").textContent = message;
    $("message").style.color = isError ? "#c0392b" : "#5267e8";
}

function currentQuery() {
    const params = new URLSearchParams();

    if ($("category").value) {
        params.set("category", $("category").value);
    }

    if ($("region").value) {
        params.set("region", $("region").value);
    }

    if ($("search").value.trim()) {
        params.set("search", $("search").value.trim());
    }

    return params.toString();
}

function fillSelect(id, values, label) {
    const select = $(id);
    select.replaceChildren(new Option(label, ""));

    values.forEach(value => {
        select.add(new Option(value, value));
    });
}

async function loadDashboard() {
    const currentRequest = ++requestNumber;

    try {
        const response = await fetch("/api/data?" + currentQuery());
        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Could not load data.");
        }

        if (currentRequest !== requestNumber) return;

        $("revenue").textContent = money(data.stats.revenue);
        $("orders").textContent =
            Number(data.stats.orders).toLocaleString("en-IN");
        $("units").textContent =
            Number(data.stats.units).toLocaleString("en-IN");
        $("average").textContent = money(data.stats.average);

        if (!filtersLoaded) {
            fillSelect(
                "category",
                data.filters.categories,
                "All Categories"
            );
            fillSelect(
                "region",
                data.filters.regions,
                "All Regions"
            );
            filtersLoaded = true;
        }

        drawCharts(data);
        drawTable(data.records);

        showMessage(`Dashboard updated: ${data.records.length} records shown.`);

    } catch (error) {
        showMessage(error.message, true);
    }
}

function drawCharts(data) {
    if (typeof Chart === "undefined") {
        showMessage(
            "Charts need an internet connection. Please refresh the page.",
            true
        );
        return;
    }

    [monthlyChart, categoryChart, productChart].forEach(chart => {
        if (chart) chart.destroy();
    });

    monthlyChart = new Chart($("monthlyChart"), {
        type: "line",
        data: {
            labels: data.monthly.labels,
            datasets: [{
                label: "Revenue",
                data: data.monthly.values,
                borderColor: "#5969e8",
                backgroundColor: "rgba(89,105,232,0.12)",
                fill: true,
                tension: 0.35
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: item => money(item.raw)
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: value => "₹" +
                            Number(value).toLocaleString("en-IN")
                    }
                },
                x: { grid: { display: false } }
            }
        }
    });

    categoryChart = new Chart($("categoryChart"), {
        type: "doughnut",
        data: {
            labels: data.categories.labels,
            datasets: [{
                data: data.categories.values,
                backgroundColor: [
                    "#5969e8", "#22b8a7", "#f5b544",
                    "#ed7189", "#8b7cf6"
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: "63%",
            plugins: {
                legend: { position: "bottom" },
                tooltip: {
                    callbacks: {
                        label: item => item.label + ": " + money(item.raw)
                    }
                }
            }
        }
    });

    productChart = new Chart($("productChart"), {
        type: "bar",
        data: {
            labels: data.products.labels,
            datasets: [{
                label: "Revenue",
                data: data.products.values,
                backgroundColor: "#6676ed",
                borderRadius: 6
            }]
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: item => money(item.raw)
                    }
                }
            },
            scales: {
                x: { beginAtZero: true },
                y: { grid: { display: false } }
            }
        }
    });
}

function drawTable(records) {
    const tbody = $("tableBody");
    tbody.replaceChildren();

    $("recordCount").textContent =
        `${records.length} matching records (maximum 200)`;

    records.forEach(record => {
        const tr = document.createElement("tr");

        const values = [
            record.order_date,
            record.product,
            record.category,
            record.region,
            Number(record.quantity).toLocaleString("en-IN"),
            money(record.unit_price),
            money(record.revenue)
        ];

        values.forEach(value => {
            const td = document.createElement("td");
            td.textContent = value;
            tr.appendChild(td);
        });

        tbody.appendChild(tr);
    });
}

$("category").addEventListener("change", loadDashboard);
$("region").addEventListener("change", loadDashboard);

$("search").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(loadDashboard, 300);
});

$("exportBtn").addEventListener("click", () => {
    window.location.href = "/api/export?" + currentQuery();
});

$("fileInput").addEventListener("change", async event => {
    const file = event.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    showMessage("Uploading CSV...");

    try {
        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.error || "Upload failed.");
        }

        $("category").value = "";
        $("region").value = "";
        $("search").value = "";
        filtersLoaded = false;

        await loadDashboard();
        showMessage(result.message);

    } catch (error) {
        showMessage(error.message, true);
    } finally {
        event.target.value = "";
    }
});

loadDashboard();
