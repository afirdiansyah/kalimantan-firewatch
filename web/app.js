/* ============================================================
   KALIMANTAN FIREWATCH
   SUPABASE + LEAFLET + CHART.JS
============================================================ */


/* ============================================================
   SUPABASE CONFIG
============================================================ */

const SUPABASE_URL =
    "https://qyylwxguhpwgqlzrqsve.supabase.co";

const SUPABASE_KEY =
    "sb_publishable_wIGLVoLrJZUXBRPcBnEF8A_0395rkQW";


const supabaseClient =
    window.supabase.createClient(
        SUPABASE_URL,
        SUPABASE_KEY
    );


/* ============================================================
   GLOBAL
============================================================ */

let map = null;

let hotspotLayer = null;

let trendChart = null;

let allHotspots = [];

let filteredHotspots = [];

let currentTheme = "dark";


/* ============================================================
   FORMAT
============================================================ */

function formatNumber(value) {

    return new Intl.NumberFormat(
        "id-ID"
    ).format(
        Number(value) || 0
    );
}


function formatFRP(value) {

    return new Intl.NumberFormat(
        "id-ID",
        {
            minimumFractionDigits: 1,
            maximumFractionDigits: 1
        }
    ).format(
        Number(value) || 0
    );
}


/* ============================================================
   GET FRP COLOR
============================================================ */

function getFireColor(frp) {

    const value =
        Number(frp) || 0;

    if (value > 100) {

        return "#9e1420";

    }

    if (value >= 50) {

        return "#ed482e";

    }

    if (value >= 10) {

        return "#f59e42";

    }

    return "#f5d76e";
}


/* ============================================================
   INITIAL MAP
============================================================ */

function initializeMap() {

    map = L.map(
        "map",
        {
            zoomControl: true,
            preferCanvas: true
        }
    );


    /* ========================================================
       DARK BASEMAP
    ========================================================= */

    const darkTiles =
        L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
            {
                attribution:
                    "&copy; OpenStreetMap &copy; CARTO",
                maxZoom: 18
            }
        );


    /* ========================================================
       LIGHT BASEMAP
    ========================================================= */

    const lightTiles =
        L.tileLayer(
            "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
            {
                attribution:
                    "&copy; OpenStreetMap &copy; CARTO",
                maxZoom: 18
            }
        );


    window.darkTiles = darkTiles;

    window.lightTiles = lightTiles;


    darkTiles.addTo(map);


    /* ========================================================
       KALIMANTAN BOUNDS
    ========================================================= */

    const kalimantanBounds =
        L.latLngBounds(
            [
                -4.4,
                108.0
            ],
            [
                4.5,
                119.6
            ]
        );


    map.fitBounds(
        kalimantanBounds,
        {
            padding:
                [20, 20]
        }
    );


    /*
       IMPORTANT:

       invalidateSize mencegah map menjadi
       blank / hanya abu-abu ketika container
       baru selesai dirender.
    */

    setTimeout(
        () => {

            map.invalidateSize();

            map.fitBounds(
                kalimantanBounds,
                {
                    padding:
                        [20, 20]
                }
            );

        },
        300
    );


    return map;
}


/* ============================================================
   LOAD SATELLITE OPTIONS
============================================================ */

async function loadSatelliteOptions() {

    const {
        data,
        error
    } = await supabaseClient

        .from("hotspots")

        .select("satellite");


    if (error) {

        console.error(
            "Satellite option error:",
            error
        );

        return;
    }


    const satellites =
        [
            ...new Set(
                (data || [])
                    .map(
                        row =>
                            row.satellite
                    )
                    .filter(Boolean)
            )
        ]
        .sort();


    const select =
        document.getElementById(
            "satellite-filter"
        );


    satellites.forEach(
        satellite => {

            const option =
                document.createElement(
                    "option"
                );

            option.value =
                satellite;

            option.textContent =
                satellite;

            select.appendChild(
                option
            );

        }
    );
}


/* ============================================================
   LOAD ALL HOTSPOTS
============================================================ */

async function loadHotspots() {

    console.log(
        "Loading hotspot data..."
    );


    const PAGE_SIZE =
        1000;

    let from = 0;

    let result = [];


    while (true) {

        const to =
            from +
            PAGE_SIZE -
            1;


        const {
            data,
            error
        } = await supabaseClient

            .from("hotspots")

            .select(`
                latitude,
                longitude,
                acq_date,
                acq_time,
                satellite,
                confidence,
                frp,
                province
            `)

            .range(
                from,
                to
            );


        if (error) {

            console.error(
                "Hotspot error:",
                error
            );

            document.getElementById(
                "map-status-text"
            ).textContent =
                "Failed to load data";

            return;
        }


        if (
            !data ||
            data.length === 0
        ) {

            break;

        }


        result.push(
            ...data
        );


        if (
            data.length <
            PAGE_SIZE
        ) {

            break;

        }


        from +=
            PAGE_SIZE;
    }


    allHotspots =
        result.filter(
            row => {

                const lat =
                    Number(
                        row.latitude
                    );

                const lon =
                    Number(
                        row.longitude
                    );


                return (
                    Number.isFinite(lat) &&
                    Number.isFinite(lon)
                );

            }
        );


    filteredHotspots =
        [...allHotspots];


    console.log(
        "Total hotspots:",
        allHotspots.length
    );


    document.getElementById(
        "map-status-text"
    ).textContent =
        `${formatNumber(allHotspots.length)} detections loaded`;


    renderHotspots(
        filteredHotspots
    );


    updateDashboardStats(
        filteredHotspots
    );
}


/* ============================================================
   CREATE FIRE MARKER
============================================================ */

function createFireMarker(
    hotspot
) {

    const lat =
        Number(
            hotspot.latitude
        );

    const lon =
        Number(
            hotspot.longitude
        );

    const frp =
        Number(
            hotspot.frp
        ) || 0;


    const color =
        getFireColor(frp);


    const marker =
        L.circleMarker(
            [
                lat,
                lon
            ],
            {

                radius:
                    frp > 100
                        ? 6
                        : frp >= 50
                        ? 5
                        : 4,

                color:
                    color,

                fillColor:
                    color,

                fillOpacity:
                    0.78,

                weight:
                    1,

                opacity:
                    0.95

            }
        );


    marker.bindPopup(`

        <span class="popup-title">
            🔥 Fire Detection
        </span>

        <table class="popup-table">

            <tr>
                <td>Province</td>
                <td>
                    ${hotspot.province ?? "-"}
                </td>
            </tr>

            <tr>
                <td>Satellite</td>
                <td>
                    ${hotspot.satellite ?? "-"}
                </td>
            </tr>

            <tr>
                <td>Date</td>
                <td>
                    ${hotspot.acq_date ?? "-"}
                </td>
            </tr>

            <tr>
                <td>Time</td>
                <td>
                    ${hotspot.acq_time ?? "-"}
                </td>
            </tr>

            <tr>
                <td>FRP</td>
                <td style="color:${color}">
                    ${formatFRP(frp)} MW
                </td>
            </tr>

            <tr>
                <td>Confidence</td>
                <td>
                    ${(hotspot.confidence ?? "-").toUpperCase()}
                </td>
            </tr>

            <tr>
                <td>Latitude</td>
                <td>
                    ${lat.toFixed(5)}
                </td>
            </tr>

            <tr>
                <td>Longitude</td>
                <td>
                    ${lon.toFixed(5)}
                </td>
            </tr>

        </table>

    `);


    return marker;
}


/* ============================================================
   RENDER HOTSPOTS
============================================================ */

function renderHotspots(
    data
) {

    if (
        hotspotLayer
    ) {

        map.removeLayer(
            hotspotLayer
        );

    }


    hotspotLayer =
        L.layerGroup();


    data.forEach(
        hotspot => {

            const marker =
                createFireMarker(
                    hotspot
                );

            marker.addTo(
                hotspotLayer
            );

        }
    );


    hotspotLayer.addTo(
        map
    );


    document.getElementById(
        "visible-hotspots"
    ).textContent =
        formatNumber(
            data.length
        );


    document.getElementById(
        "map-status-text"
    ).textContent =
        `${formatNumber(data.length)} hotspots visible`;


    console.log(
        "Rendered:",
        data.length
    );
}


/* ============================================================
   APPLY FILTER
============================================================ */

function applyFilters() {

    const date =
        document.getElementById(
            "fire-date"
        ).value;


    const province =
        document.getElementById(
            "province-filter"
        ).value;


    const satellite =
        document.getElementById(
            "satellite-filter"
        ).value;


    const confidence =
        document.getElementById(
            "confidence-filter"
        ).value;


    const minimumFRP =
        Number(
            document.getElementById(
                "frp-filter"
            ).value
        ) || 0;


    filteredHotspots =
        allHotspots.filter(
            hotspot => {


                /* DATE */

                if (
                    date &&
                    hotspot.acq_date !== date
                ) {

                    return false;

                }


                /* PROVINCE */

                if (
                    province !== "all" &&
                    String(
                        hotspot.province
                    ).trim() !== province
                ) {

                    return false;

                }


                /* SATELLITE */

                if (
                    satellite !== "all" &&
                    String(
                        hotspot.satellite
                    ).trim() !== satellite
                ) {

                    return false;

                }


                /* CONFIDENCE */

                if (
                    confidence !== "all" &&
                    String(
                        hotspot.confidence
                    ).toLowerCase() !==
                    confidence.toLowerCase()
                ) {

                    return false;

                }


                /* FRP */

                const frp =
                    Number(
                        hotspot.frp
                    ) || 0;


                if (
                    frp <
                    minimumFRP
                ) {

                    return false;

                }


                return true;

            }
        );


    renderHotspots(
        filteredHotspots
    );


    updateDashboardStats(
        filteredHotspots
    );


    updateMapView(
        filteredHotspots
    );
}


/* ============================================================
   UPDATE MAP VIEW
============================================================ */

function updateMapView(
    data
) {

    if (
        !data.length
    ) {

        return;

    }


    /*
       Kalau filter provinsi digunakan,
       zoom ke data hasil filter.
    */

    const points =
        data
            .map(
                row =>
                    [
                        Number(
                            row.latitude
                        ),
                        Number(
                            row.longitude
                        )
                    ]
            )
            .filter(
                point =>
                    Number.isFinite(
                        point[0]
                    ) &&
                    Number.isFinite(
                        point[1]
                    )
            );


    if (
        !points.length
    ) {

        return;

    }


    const bounds =
        L.latLngBounds(
            points
        );


    map.fitBounds(
        bounds,
        {
            padding:
                [35, 35],

            maxZoom:
                10
        }
    );
}


/* ============================================================
   UPDATE DASHBOARD STATS
============================================================ */

function updateDashboardStats(
    data
) {

    const fireEvents =
        data.length;


    const detections =
        data.length;


    const totalFRP =
        data.reduce(
            (
                sum,
                row
            ) =>
                sum +
                (
                    Number(
                        row.frp
                    ) || 0
                ),
            0
        );


    const provinces =
        new Set(
            data
                .map(
                    row =>
                        row.province
                )
                .filter(Boolean)
        );


    document.getElementById(
        "total-events"
    ).textContent =
        formatNumber(
            fireEvents
        );


    document.getElementById(
        "total-detections"
    ).textContent =
        formatNumber(
            detections
        );


    document.getElementById(
        "total-frp"
    ).textContent =
        formatFRP(
            totalFRP
        );


    document.getElementById(
        "total-provinces"
    ).textContent =
        provinces.size;
}


/* ============================================================
   LOAD DAILY SUMMARY
============================================================ */

async function loadDailySummary() {

    const {
        data,
        error
    } = await supabaseClient

        .from(
            "daily_fire_summary"
        )

        .select("*")

        .order(
            "date",
            {
                ascending:
                    true
            }
        );


    if (error) {

        console.error(
            "Daily summary:",
            error
        );

        return;

    }


    if (
        !data ||
        !data.length
    ) {

        return;

    }


    renderTrendChart(
        data
    );
}


/* ============================================================
   TREND CHART
============================================================ */

function renderTrendChart(
    data
) {

    const canvas =
        document.getElementById(
            "fireTrendChart"
        );


    if (
        !canvas ||
        typeof Chart ===
        "undefined"
    ) {

        return;

    }


    const labels =
        data.map(
            row =>
                row.date
        );


    const events =
        data.map(
            row =>
                Number(
                    row.fire_events
                ) || 0
        );


    const detections =
        data.map(
            row =>
                Number(
                    row.detections
                ) || 0
        );


    if (
        trendChart
    ) {

        trendChart.destroy();

    }


    trendChart =
        new Chart(
            canvas,
            {

                type:
                    "line",

                data: {

                    labels:

                        labels,

                    datasets: [

                        {

                            label:
                                "Fire Events",

                            data:
                                events,

                            borderColor:
                                "#ff4a38",

                            backgroundColor:
                                "rgba(255,74,56,.10)",

                            borderWidth:
                                2,

                            pointRadius:
                                2,

                            tension:
                                .35,

                            fill:
                                true

                        },

                        {

                            label:
                                "Detections",

                            data:
                                detections,

                            borderColor:
                                "#ff9b38",

                            backgroundColor:
                                "transparent",

                            borderWidth:
                                1.5,

                            pointRadius:
                                1.5,

                            tension:
                                .35,

                            fill:
                                false

                        }

                    ]

                },

                options: {

                    responsive:
                        true,

                    maintainAspectRatio:
                        false,

                    interaction: {

                        mode:
                            "index",

                        intersect:
                            false

                    },

                    plugins: {

                        legend: {

                            display:
                                true,

                            position:
                                "top",

                            labels: {

                                color:
                                    currentTheme ===
                                    "dark"
                                        ? "#e9d8d4"
                                        : "#59443c",

                                font: {

                                    size:
                                        8

                                },

                                boxWidth:
                                    8

                            }

                        }

                    },

                    scales: {

                        x: {

                            ticks: {

                                color:
                                    currentTheme ===
                                    "dark"
                                        ? "#a9938d"
                                        : "#766862",

                                font: {

                                    size:
                                        7

                                },

                                maxTicksLimit:
                                    6

                            },

                            grid: {

                                display:
                                    false

                            }

                        },

                        y: {

                            beginAtZero:
                                true,

                            ticks: {

                                color:
                                    currentTheme ===
                                    "dark"
                                        ? "#a9938d"
                                        : "#766862",

                                font: {

                                    size:
                                        7

                                }

                            },

                            grid: {

                                color:
                                    currentTheme ===
                                    "dark"
                                        ? "rgba(255,255,255,.05)"
                                        : "rgba(0,0,0,.05)"

                            }

                        }

                    }

                }

            }
        );
}


/* ============================================================
   PROVINCE STATISTICS
============================================================ */

async function loadProvinceStatistics() {

    const {
        data,
        error
    } = await supabaseClient

        .from(
            "province_fire_summary"
        )

        .select("*")

        .order(
            "fire_events",
            {
                ascending:
                    false
            }
        );


    if (error) {

        console.error(
            "Province:",
            error
        );

        return;

    }


    const container =
        document.getElementById(
            "province-chart"
        );


    if (
        !data ||
        !data.length
    ) {

        container.innerHTML =
            `<div class="loading">
                No province data
             </div>`;

        return;

    }


    const maxEvents =
        Math.max(
            ...data.map(
                row =>
                    Number(
                        row.fire_events
                    ) || 0
            )
        );


    container.innerHTML =
        "";


    data.forEach(
        row => {

            const events =
                Number(
                    row.fire_events
                ) || 0;


            const detections =
                Number(
                    row.detections
                ) || 0;


            const frp =
                Number(
                    row.total_frp
                ) || 0;


            const percentage =
                maxEvents > 0
                    ? (
                        events /
                        maxEvents
                    ) * 100
                    : 0;


            const item =
                document.createElement(
                    "div"
                );


            item.className =
                "ranking-item";


            item.innerHTML = `

                <div class="ranking-top">

                    <span class="ranking-name">
                        ${row.province ?? "-"}
                    </span>

                    <span class="ranking-value">
                        ${formatNumber(events)}
                    </span>

                </div>

                <div class="ranking-bar">

                    <div
                        class="ranking-fill"
                        style="width:${percentage}%">
                    </div>

                </div>

                <div class="ranking-detail">

                    <span>
                        ${formatNumber(detections)}
                        detections
                    </span>

                    <span>
                        ${formatFRP(frp)}
                        MW
                    </span>

                </div>
            `;


            container.appendChild(
                item
            );

        }
    );
}


/* ============================================================
   SATELLITE STATISTICS
============================================================ */

async function loadSatelliteStatistics() {

    const {
        data,
        error
    } = await supabaseClient

        .from(
            "satellite_fire_summary"
        )

        .select("*")

        .order(
            "detections",
            {
                ascending:
                    false
            }
        );


    if (error) {

        console.error(
            "Satellite:",
            error
        );

        return;

    }


    const container =
        document.getElementById(
            "satellite-chart"
        );


    if (
        !data ||
        !data.length
    ) {

        container.innerHTML =
            `<div class="loading">
                No satellite data
             </div>`;

        return;

    }


    const maxDetections =
        Math.max(
            ...data.map(
                row =>
                    Number(
                        row.detections
                    ) || 0
            )
        );


    container.innerHTML =
        "";


    data.forEach(
        row => {

            const detections =
                Number(
                    row.detections
                ) || 0;


            const fireEvents =
                Number(
                    row.fire_events
                ) || 0;


            const frp =
                Number(
                    row.total_frp
                ) || 0;


            const percentage =
                maxDetections > 0
                    ? (
                        detections /
                        maxDetections
                    ) * 100
                    : 0;


            const item =
                document.createElement(
                    "div"
                );


            item.className =
                "ranking-item";


            item.innerHTML = `

                <div class="ranking-top">

                    <span class="ranking-name">
                        🛰 ${row.satellite ?? "-"}
                    </span>

                    <span class="ranking-value">
                        ${formatNumber(detections)}
                    </span>

                </div>

                <div class="ranking-bar">

                    <div
                        class="ranking-fill"
                        style="width:${percentage}%">
                    </div>

                </div>

                <div class="ranking-detail">

                    <span>
                        ${formatNumber(fireEvents)}
                        events
                    </span>

                    <span>
                        ${formatFRP(frp)}
                        MW
                    </span>

                </div>
            `;


            container.appendChild(
                item
            );

        }
    );
}


/* ============================================================
   RESET FILTER
============================================================ */

function resetFilters() {

    document.getElementById(
        "fire-date"
    ).value = "";


    document.getElementById(
        "province-filter"
    ).value =
        "all";


    document.getElementById(
        "satellite-filter"
    ).value =
        "all";


    document.getElementById(
        "confidence-filter"
    ).value =
        "all";


    document.getElementById(
        "frp-filter"
    ).value =
        "0";


    filteredHotspots =
        [...allHotspots];


    renderHotspots(
        filteredHotspots
    );


    updateDashboardStats(
        filteredHotspots
    );


    const bounds =
        L.latLngBounds(
            [
                -4.4,
                108.0
            ],
            [
                4.5,
                119.6
            ]
        );


    map.fitBounds(
        bounds,
        {
            padding:
                [20,20]
        }
    );
}


/* ============================================================
   THEME
============================================================ */

function toggleTheme() {

    currentTheme =
        currentTheme ===
        "dark"
            ? "light"
            : "dark";


    document.documentElement
        .setAttribute(
            "data-theme",
            currentTheme
        );


    if (
        map
    ) {

        if (
            currentTheme ===
            "dark"
        ) {

            if (
                map.hasLayer(
                    window.lightTiles
                )
            ) {

                map.removeLayer(
                    window.lightTiles
                );

            }

            window.darkTiles.addTo(
                map
            );

        } else {

            if (
                map.hasLayer(
                    window.darkTiles
                )
            ) {

                map.removeLayer(
                    window.darkTiles
                );

            }

            window.lightTiles.addTo(
                map
            );

        }

    }


    document.getElementById(
        "theme-toggle"
    ).textContent =
        currentTheme ===
        "dark"
            ? "☀ Light"
            : "◐ Dark";


    if (
        trendChart
    ) {

        loadDailySummary();

    }
}


/* ============================================================
   REFRESH
============================================================ */

async function refreshDashboard() {

    const button =
        document.getElementById(
            "refresh-button"
        );


    button.textContent =
        "↻ Loading...";


    try {

        await loadHotspots();

        await loadDailySummary();

        await loadProvinceStatistics();

        await loadSatelliteStatistics();

    } finally {

        button.textContent =
            "↻ Refresh";

    }
}


/* ============================================================
   EVENTS
============================================================ */

function setupEvents() {

    document.getElementById(
        "apply-filter"
    ).addEventListener(
        "click",
        applyFilters
    );


    document.getElementById(
        "reset-filter"
    ).addEventListener(
        "click",
        resetFilters
    );


    document.getElementById(
        "theme-toggle"
    ).addEventListener(
        "click",
        toggleTheme
    );


    document.getElementById(
        "refresh-button"
    ).addEventListener(
        "click",
        refreshDashboard
    );


    /*
       Enter pada FRP juga langsung apply.
    */

    document.getElementById(
        "frp-filter"
    ).addEventListener(
        "keydown",
        event => {

            if (
                event.key ===
                "Enter"
            ) {

                applyFilters();

            }

        }
    );

}


/* ============================================================
   INITIALIZE
============================================================ */

async function init() {

    console.log(
        "🔥 Kalimantan FireWatch starting..."
    );


    /*
       Dark sebagai default.
    */

    document.documentElement
        .setAttribute(
            "data-theme",
            "dark"
        );


    /*
       Map HARUS dibuat setelah DOM siap.
    */

    initializeMap();


    setupEvents();


    /*
       Load dropdown satellite
    */

    await loadSatelliteOptions();


    /*
       Load seluruh hotspot
    */

    await loadHotspots();


    /*
       Load analytics
    */

    await loadDailySummary();

    await loadProvinceStatistics();

    await loadSatelliteStatistics();


    /*
       Pastikan ukuran map benar.
    */

    setTimeout(
        () => {

            map.invalidateSize();

        },
        500
    );


    console.log(
        "🔥 FireWatch ready."
    );
}


/* ============================================================
   START
============================================================ */

document.addEventListener(
    "DOMContentLoaded",
    init
);