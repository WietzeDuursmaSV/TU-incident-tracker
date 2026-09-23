
const inputs = [...document.querySelectorAll('input[type="file"]')];
const status = document.querySelector('#file-status');


// ---------------------------------------------------------
// Bestand selecteren
// ---------------------------------------------------------

inputs.forEach(input => {
    input.addEventListener('change', () => {
        updateFileStatus();

        const fileName = document.querySelector(`#${input.id}-name`);

        if (fileName && input.files[0]) {
            fileName.textContent = input.files[0].name;
        }
    });
});

function updateFileStatus() {
    if (!status) return;

    const selected = inputs.filter(input => input.files.length).length;

    if (selected === 0) {
        status.textContent = 'Nog geen bestanden geselecteerd';
    } else {
        status.textContent = `${selected} van 2 bestanden geselecteerd`;
    }
}


// ---------------------------------------------------------
// Drag & Drop
// ---------------------------------------------------------

function setupDropZone(cardSelector, inputId, nameId) {
    const card = document.querySelector(cardSelector);
    const input = document.getElementById(inputId);
    const fileName = document.getElementById(nameId);

    if (!card || !input) return;


    // Drag over
    card.addEventListener('dragover', event => {
        event.preventDefault();
        event.stopPropagation();

        card.classList.add('drag-over');
    });


    // Drag verlaten
    card.addEventListener('dragleave', event => {
        event.preventDefault();
        event.stopPropagation();

        if (!card.contains(event.relatedTarget)) {
            card.classList.remove('drag-over');
        }
    });


    // Bestand droppen
    card.addEventListener('drop', event => {
        event.preventDefault();
        event.stopPropagation();

        card.classList.remove('drag-over');

        const files = event.dataTransfer.files;

        if (!files.length) {
            return;
        }

        const file = files[0];


        // Alleen CSV toestaan
        if (!file.name.toLowerCase().endsWith('.csv')) {
            alert('Selecteer een CSV-bestand.');
            return;
        }


        // Bestand aan input koppelen
        const dataTransfer = new DataTransfer();

        dataTransfer.items.add(file);

        input.files = dataTransfer.files;


        // Bestandsnaam tonen
        if (fileName) {
            fileName.textContent = file.name;
        }

        updateFileStatus();
    });
}


// SPO dropzone
setupDropZone(
    '.file-card[for="spo_file"]',
    'spo_file',
    'spo_file-name'
);


// SNOW dropzone
setupDropZone(
    '.file-card[for="snow_file"]',
    'snow_file',
    'snow_file-name'
);


// ---------------------------------------------------------
// Onbeantwoorde SNOW matches tonen/verbergen
// ---------------------------------------------------------

const table = document.querySelector('.table-wrap table');
const unmatchedToggle = document.querySelector('#show-unmatched');

function updateUnmatchedRows() {
    if (!unmatchedToggle || !table) return;

    table
        .querySelectorAll('tbody tr[data-snow-match="0"]')
        .forEach(row => {
            row.hidden = unmatchedToggle.checked;
        });
}

unmatchedToggle?.addEventListener(
    'change',
    updateUnmatchedRows
);

updateUnmatchedRows();


// ---------------------------------------------------------
// SLO voortgang
// ---------------------------------------------------------

document
    .querySelectorAll('.slo-fill[data-progress]')
    .forEach(fill => {

        const rawProgress = Number(
            fill.dataset.progress || 0
        );

        const progress = Math.max(
            0,
            Math.min(rawProgress, 100)
        );

        fill.style.width = `${progress}%`;

        fill.classList.add(
            fill.dataset.withinSlo === '1'
                ? 'is-green'
                : 'is-red'
        );
    });


// ---------------------------------------------------------
// Tabel sorteren
// ---------------------------------------------------------

const sortableHeaders = [
    ...document.querySelectorAll('.sort-button')
];

const missingValue = '—';

function sortValue(value) {

    const normalized = value.trim();

    if (
        !normalized ||
        normalized === missingValue
    ) {
        return {
            type: 'empty',
            value: ''
        };
    }


    // Getal
    const decimalNumber = normalized.match(
        /^-?\d+(?:[.,]\d+)?$/
    );

    if (decimalNumber) {
        return {
            type: 'number',
            value: Number(
                normalized.replace(',', '.')
            )
        };
    }


    // Datum
    const date = normalized.match(
        /^(\d{1,2})[\/-](\d{1,2})[\/-](\d{4})(?:\s+(\d{1,2}):(\d{2}))?/
    );

    if (date) {
        return {
            type: 'date',
            value: new Date(
                Number(date[3]),
                Number(date[2]) - 1,
                Number(date[1]),
                Number(date[4] || 0),
                Number(date[5] || 0)
            ).getTime()
        };
    }


    // Prioriteit
    const priority = normalized.match(/^(\d+)/);

    if (priority) {
        return {
            type: 'number',
            value: Number(priority[1])
        };
    }


    // Tekst
    return {
        type: 'text',
        value: normalized.toLocaleLowerCase('nl')
    };
}


sortableHeaders.forEach(header => {

    header.addEventListener('click', () => {

        if (!table || !table.tBodies[0]) {
            return;
        }

        const column = Number(
            header.dataset.column
        );

        const currentDirection =
            header.getAttribute('aria-sort') === 'ascending'
                ? 'descending'
                : 'ascending';

        const directionMultiplier =
            currentDirection === 'ascending'
                ? 1
                : -1;


        const rows = [
            ...table.tBodies[0].rows
        ];


        rows.sort((leftRow, rightRow) => {

            const leftCell =
                leftRow.cells[column];

            const rightCell =
                rightRow.cells[column];


            const leftSource =
                leftCell.dataset.sort ||
                leftCell.textContent;

            const rightSource =
                rightCell.dataset.sort ||
                rightCell.textContent;


            const leftValue =
                sortValue(leftSource);

            const rightValue =
                sortValue(rightSource);


            // Lege waarden onderaan
            if (
                leftValue.type === 'empty' &&
                rightValue.type !== 'empty'
            ) {
                return 1;
            }

            if (
                rightValue.type === 'empty' &&
                leftValue.type !== 'empty'
            ) {
                return -1;
            }


            // Getallen en datums
            if (
                (
                    leftValue.type === 'number' &&
                    rightValue.type === 'number'
                ) ||
                (
                    leftValue.type === 'date' &&
                    rightValue.type === 'date'
                )
            ) {
                return (
                    leftValue.value -
                    rightValue.value
                ) * directionMultiplier;
            }


            // Tekst
            return String(leftValue.value)
                .localeCompare(
                    String(rightValue.value),
                    'nl'
                ) * directionMultiplier;
        });


        // Rijen opnieuw toevoegen
        rows.forEach(row => {
            table.tBodies[0].appendChild(row);
        });


        // Alle sort indicators resetten
        sortableHeaders.forEach(otherHeader => {

            otherHeader.removeAttribute(
                'aria-sort'
            );

            const indicator =
                otherHeader.querySelector(
                    '.sort-indicator'
                );

            if (indicator) {
                indicator.textContent = '↕';
            }
        });


        // Actieve sortering instellen
        header.setAttribute(
            'aria-sort',
            currentDirection
        );

        const indicator =
            header.querySelector(
                '.sort-indicator'
            );

        if (indicator) {
            indicator.textContent =
                currentDirection === 'ascending'
                    ? '↑'
                    : '↓';
        }
    });
});


// ---------------------------------------------------------
// Match History Tijdlijn
// ---------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {

    const timeline = document.querySelector('#match-timeline');

    if (!timeline) {
        return;
    }


    // ---------------------------------------------------------
    // LocalStorage uitlezen
    // ---------------------------------------------------------

    function getMatchHistory() {
        const savedData = localStorage.getItem('match_history');

        if (!savedData) {
            return [];
        }

        try {
            return JSON.parse(savedData);
        } catch (error) {
            console.error(
                'Fout bij uitlezen van match_history:',
                error
            );

            return [];
        }
    }


    // ---------------------------------------------------------
    // Datum formatteren
    // ---------------------------------------------------------

    function formatDate(timestamp) {

        const date = new Date(timestamp);

        return date.toLocaleDateString('nl-NL', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric'
        });
    }


    // ---------------------------------------------------------
    // Tijdlijn renderen
    // ---------------------------------------------------------

    function renderMatchTimeline() {

        const history = getMatchHistory().filter(
            entry => Number(entry.total_spo_tickets) > 0
        );

        timeline.innerHTML = '';


        if (!history.length) {

            timeline.innerHTML = `
                <div class="timeline-empty">
                    Nog geen matchhistorie beschikbaar.
                </div>
            `;

            return;
        }


        // -----------------------------------------------------
        // Chart
        // -----------------------------------------------------

        const chart = document.createElement('div');
        chart.className = 'timeline-chart';


        // -----------------------------------------------------
        // Y-as labels
        // -----------------------------------------------------

        const yAxis = document.createElement('div');
        yAxis.className = 'timeline-y-axis';

        yAxis.innerHTML = `
  
        `;

        chart.appendChild(yAxis);


        // -----------------------------------------------------
        // Grafiek
        // -----------------------------------------------------

        const graph = document.createElement('div');
        graph.className = 'timeline-graph';


        // Horizontale hulplijnen
        const grid = document.createElement('div');
        grid.className = 'timeline-grid';

        grid.innerHTML = `
           
            <span></span>
            <span></span>
            <span></span>
        `;

        graph.appendChild(grid);


        // -----------------------------------------------------
        // Balken
        // -----------------------------------------------------

        const bars = document.createElement('div');
        bars.className = 'timeline-bars';


        history.forEach((entry) => {

            const totalTickets =
                Number(entry.total_spo_tickets) || 0;


            // Waarde beperken tot 0 - 80
            const value = Math.min(
                Math.max(totalTickets, 0),
                80
            );


            // Hoogte als percentage van 80
            const height = (value / 80) * 100;


            const item = document.createElement('div');
            item.className = 'timeline-item';


            item.innerHTML = `
                <div class="timeline-bar-area">

                    <div
                        class="timeline-bar"
                        style="height: ${height}%"
                        title="${totalTickets} SPO tickets"
                    >
                        <span class="timeline-value">
                            ${totalTickets}
                        </span>
                    </div>

                </div>

                <div class="timeline-date">
                    ${formatDate(entry.timestamp)}
                </div>
            `;


            bars.appendChild(item);
        });


        graph.appendChild(bars);

        chart.appendChild(graph);

        timeline.appendChild(chart);
    }


    // ---------------------------------------------------------
    // Initialiseren
    // ---------------------------------------------------------

    renderMatchTimeline();

});

async function searchKB() {
  const query = document.getElementById('kb-query').value;
  if (!query) return;

  document.getElementById('kb-loading').style.display = 'block';
  document.getElementById('kb-results').style.display = 'none';

  const response = await fetch('/search_kb', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: query })
  });

  const data = await response.json();
  document.getElementById('kb-loading').style.display = 'none';

  if (data.error) {
    alert(data.error);
    return;
  }

  document.getElementById('kb-answer').innerText = data.answer;
  
  const sourcesContainer = document.getElementById('kb-sources');
  sourcesContainer.innerHTML = '';
  
  data.sources.forEach(src => {
    const card = document.createElement('div');
    card.style.border = '1px solid #ddd';
    card.style.padding = '10px';
    card.style.marginBottom = '10px';
    card.innerHTML = `<strong>${src.number}</strong> - ${src.short_description}<br><small><b>Oplossing:</b> ${src.close_notes || 'Geen notitie'}</small>`;
    sourcesContainer.appendChild(card);
  });

  document.getElementById('kb-results').style.display = 'block';
}

document.addEventListener('DOMContentLoaded', () => {
  const pills = document.querySelectorAll('.filter-pill');
  const containers = document.querySelectorAll('.snow-container');

  pills.forEach((pill) => {
    pill.addEventListener('click', () => {
      pills.forEach((p) => p.classList.remove('is-active'));
      pill.classList.add('is-active');

      const filter = pill.dataset.filter;

      containers.forEach((container) => {
        const matches = filter === 'all' || container.dataset.assignedTo === filter;
        container.style.display = matches ? '' : 'none';
      });
    });
  });
});

// ---------------------------------------------------------
// Kanban filter op assigned_to
// ---------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {

    const filterContainer = document.querySelector('#assigned-filter');
    const containers = [
        ...document.querySelectorAll('.snow-container')
    ];

    if (!filterContainer || !containers.length) {
        return;
    }


    // -----------------------------------------------------
    // Unieke toegewezen medewerkers ophalen
    // -----------------------------------------------------

    const assignedUsers = [
        ...new Set(
            containers
                .map(container =>
                    (container.dataset.assignedTo || '').trim()
                )
                .filter(Boolean)
        )
    ].sort((a, b) =>
        a.localeCompare(b, 'nl')
    );


    // -----------------------------------------------------
    // "Alle" filter
    // -----------------------------------------------------

    const allButton = document.createElement('button');

    allButton.type = 'button';
    allButton.className = 'filter-pill is-active';
    allButton.dataset.filter = 'all';
    allButton.textContent = 'Iedereen';

    filterContainer.appendChild(allButton);


    // -----------------------------------------------------
    // Filterknoppen per medewerker
    // -----------------------------------------------------

    assignedUsers.forEach(user => {

        const button = document.createElement('button');

        button.type = 'button';
        button.className = 'filter-pill';
        button.dataset.filter = user;
        button.textContent = user;

        filterContainer.appendChild(button);
    });


    const pills = [
        ...filterContainer.querySelectorAll('.filter-pill')
    ];


     // -----------------------------------------------------
    // Filter toepassen
    // -----------------------------------------------------

    function applyFilter(filter) {

        containers.forEach(container => {

            const assignedTo =
                (container.dataset.assignedTo || '').trim();

            const matches =
                filter === 'all' ||
                assignedTo === filter;

            container.style.display =
                matches ? '' : 'none';
        });


        // Lege statussecties verbergen + tellers bijwerken
        document
            .querySelectorAll('.status-section')
            .forEach(section => {

                const visibleCards = [
                    ...section.querySelectorAll('.snow-container')
                ].filter(card =>
                    card.style.display !== 'none'
                );

                section.style.display =
                    visibleCards.length ? '' : 'none';

                const countBadge =
                    section.querySelector('.count-badge');

                if (countBadge) {
                    countBadge.textContent = visibleCards.length;
                }
            });
    }

    // -----------------------------------------------------
    // Klik op filter
    // -----------------------------------------------------

    pills.forEach(pill => {

        pill.addEventListener('click', () => {

            pills.forEach(otherPill => {
                otherPill.classList.remove('is-active');
            });

            pill.classList.add('is-active');

            applyFilter(
                pill.dataset.filter || 'all'
            );
        });
    });


    // -----------------------------------------------------
    // Initieel alles tonen
    // -----------------------------------------------------

    applyFilter('all');
});
    // -----------------------------------------------------
    // User initials in badges
    // -----------------------------------------------------
document.querySelectorAll('.user-badge').forEach(badge => {
    const name = badge.textContent.trim();

    if (!name || name === '—') {
        return;
    }

    const parts = name.split(/\s+/);

    if (parts.length >= 2) {
        badge.textContent =
            parts[0].charAt(0).toUpperCase() +
            parts[parts.length - 1].charAt(0).toUpperCase();
    } else {
        badge.textContent = parts[0].charAt(0).toUpperCase();
    }
});

// ---------------------------------------------------------
// Incident detail dialoog
// ---------------------------------------------------------

const incidentDialog = document.getElementById('incident-dialog');

if (incidentDialog) {
    const dialogTitle = document.getElementById('incident-dialog-title');
    const dialogLink = document.getElementById('incident-dialog-link');
    const dialogPriority = document.getElementById('incident-dialog-priority');
    const dialogState = document.getElementById('incident-dialog-state');
    const dialogGroup = document.getElementById('incident-dialog-group');
    const dialogAssigned = document.getElementById('incident-dialog-assigned');
    const dialogSummary = document.getElementById('incident-dialog-summary');

    const priorityClassByGroup = {
        Kritiek: 'priority-critical',
        Hoog: 'priority-high',
        Gemiddeld: 'priority-medium',
        Laag: 'priority-low',
    };

    function openIncidentDialog(card) {
        const number = card.dataset.number || '';

        dialogTitle.textContent = number || 'Incident';

        if (number) {
            dialogLink.textContent = number;
            dialogLink.href = `https://soneparprod.service-now.com/incident.do?sysparm_query=number=${encodeURIComponent(number)}`;
            dialogLink.hidden = false;
        } else {
            dialogLink.hidden = true;
        }

        const priorityGroup = card.dataset.priorityGroup || '';
        dialogPriority.textContent = card.dataset.priority || '—';
        dialogPriority.className = `priority ${priorityClassByGroup[priorityGroup] || ''}`.trim();

        dialogState.textContent = card.dataset.state || '—';
        dialogGroup.textContent = card.dataset.assignmentGroup || '—';
        dialogAssigned.textContent = card.dataset.assignedTo || '—';
        dialogSummary.textContent = card.dataset.summary || '—';

        incidentDialog.showModal();
    }

    document.querySelectorAll('.snow-container[role="button"]').forEach(card => {
        card.addEventListener('click', event => {
            if (event.target.closest('a')) return; // laat de SNOW-link gewoon werken
            openIncidentDialog(card);
        });

        card.addEventListener('keydown', event => {
            if (event.key === 'Enter' || event.key === ' ') {
                event.preventDefault();
                openIncidentDialog(card);
            }
        });
    });

    // Klik op de backdrop sluit de dialoog
    incidentDialog.addEventListener('click', event => {
        if (event.target === incidentDialog) incidentDialog.close();
    });
}