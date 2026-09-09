
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
            row.hidden = !unmatchedToggle.checked;
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

