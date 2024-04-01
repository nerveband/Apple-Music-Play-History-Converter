const inputFile = document.getElementById('input-file');
const radioButtons = document.querySelectorAll('input[name="file-type"]');
const convertButton = document.getElementById('convert-button');
const outputText = document.getElementById('output-text');
const resultMessage = document.getElementById('result-message');
const fileTypeMessage = document.getElementById('file-type-message');
const fileInfoMessage = document.getElementById('file-info-message');
const progressBar = document.getElementById('progress-bar');
const copyButton = document.getElementById('copy-button');
const csvTableBody = document.querySelector('#csv-table tbody');
const itunesApiCheckbox = document.getElementById('itunes-api-check');

radioButtons.forEach(radio => {
    radio.addEventListener('change', handleRadioChange);
});

inputFile.addEventListener('change', handleFileSelect);
convertButton.addEventListener('click', convertCSV);
copyButton.addEventListener('click', copyToClipboard);

function handleFileSelect() {
    const file = inputFile.files[0];
    if (file) {
        const fileSize = file.size / 1024 / 1024; // File size in MB
        fileInfoMessage.innerHTML = `Selected file: ${file.name} (${fileSize.toFixed(2)} MB). <mark>Please be patient, this may take several seconds to process.</mark>`;
        autoSelectFileType(file.name);
    }
}

function handleRadioChange() {
    const playActivityRadio = document.getElementById('play-activity');

    if (playActivityRadio.checked && playActivityRadio.disabled) {
        playActivityRadio.checked = false;
    }

    updateButtonState();
}

function updateButtonState() {
    const file = inputFile.files[0];
    const selectedRadio = document.querySelector('input[name="file-type"]:checked');
    convertButton.disabled = !(selectedRadio && file);
}

function autoSelectFileType(fileName) {
    if (fileName.includes('Play Activity')) {
        document.getElementById('play-activity').checked = true;
    } else if (fileName.includes('Recently Played Tracks')) {
        document.getElementById('recently-played').checked = true;
    } else if (fileName.includes('Play History Daily Tracks')) {
        document.getElementById('play-history').checked = true;
    }
    handleRadioChange();
}

function convertCSV() {
    const file = inputFile.files[0];
    const selectedRadio = document.querySelector('input[name="file-type"]:checked');
    if (!selectedRadio || !file) {
        console.log('File type or file not selected');
        return;
    }

    // Update button state and text
    convertButton.disabled = true;
    convertButton.setAttribute('aria-busy', 'true');
    convertButton.textContent = 'Converting...';
    convertButton.classList.add('disabled');

    outputText.value = '';
    resultMessage.textContent = '';
    fileTypeMessage.textContent = '';

    const batchSize = 10000; // Process 10,000 rows at a time
    let currentBatch = [];
    let convertedData = [];

    Papa.parse(file, {
        header: true,
        skipEmptyLines: true,
        worker: true,
        chunkSize: 10000,
        chunk: async function(results, parser) {
            currentBatch = currentBatch.concat(results.data);
            if (currentBatch.length >= batchSize) {
                const batchConvertedData = await convertData(currentBatch, selectedRadio.value);
                convertedData = convertedData.concat(batchConvertedData);
                currentBatch = [];
            }
        },
        complete: async function() {
            if (currentBatch.length > 0) {
                const { convertedData, successCount } = await convertData(currentBatch, selectedRadio.value);
                displayOutput(convertedData);
                resultMessage.textContent = `Conversion complete. ${successCount} tracks processed successfully.`;
            }

            // Update button state and text after conversion
            convertButton.disabled = false;
            convertButton.removeAttribute('aria-busy');
            convertButton.textContent = 'Convert';
            convertButton.classList.remove('disabled');
        },
        error: function(error) {
            console.error('Parsing Error:', error);
            resultMessage.textContent = 'Error: ' + error.message;

            // Update button state and text on error
            convertButton.disabled = false;
            convertButton.removeAttribute('aria-busy');
            convertButton.textContent = 'Convert';
            convertButton.classList.remove('disabled');
        }
    });
}


async function convertData(data, fileType) {
    let convertedData = [];
    let currentTimestamp = new Date();
    let successCount = 0;

    if (fileType === 'play-history') {
        for (let i = data.length - 1; i >= 1; i--) {
            const row = data[i];
            const trackInfo = row['Track Description'] ? row['Track Description'].split(' - ') : [];
            const artist = trackInfo[0] || '';
            const track = trackInfo.slice(-1)[0] || '';
            const album = '';
            const duration = Math.floor(parseInt(row['Play Duration Milliseconds'] || '180000', 10) / 1000);
            const convertedRow = [artist, track, album, formatTimestamp(currentTimestamp), artist, duration.toString()];
            convertedData.push(convertedRow);
            currentTimestamp = subtractDuration(currentTimestamp, duration);
        }
    } else if (fileType === 'recently-played') {
        for (let i = data.length - 1; i >= 1; i--) {
            const row = data[i];
            const trackInfo = row['Track Description'] ? row['Track Description'].split(' - ') : [];
            const artist = trackInfo[0] || '';
            const track = trackInfo.slice(-1)[0] || '';
            const album = row['Container Description'] || '';
            const duration = Math.floor(parseInt(row['Media duration in millis'] || '180000') / 1000);
            const convertedRow = [artist, track, album, formatTimestamp(currentTimestamp), artist, duration.toString()];
            convertedData.push(convertedRow);
            currentTimestamp = subtractDuration(currentTimestamp, duration);
        }
    } else if (fileType === 'play-activity') {
        const chunkSize = 1000; // Process 1000 rows at a time
        const totalRows = data.length;
        let processedRows = 0;

        while (processedRows < totalRows) {
            const chunkEnd = Math.min(processedRows + chunkSize, totalRows);
            const chunk = data.slice(processedRows, chunkEnd);
            const chunkConvertedData = [];

            for (const row of chunk) {
              const track = row['Song Name'] || '';
              const album = row['Album Name'] || '';
              const duration = Math.floor(parseInt(row['Media Duration In Milliseconds'] || '180000') / 1000);

              if (itunesApiCheckbox.checked) {
                try {
                  const artist = await searchArtist(track, album);
                  const convertedRow = [artist, track, album, formatTimestamp(currentTimestamp), artist, duration.toString()];
                  chunkConvertedData.push(convertedRow.map(cell => `"${cell}"`).join(', '));
                  currentTimestamp = subtractDuration(currentTimestamp, duration);
                  successCount++;
                } catch (error) {
                  console.error('Error searching for artist:', error);
                }
              } else {
                const convertedRow = ['', track, album, formatTimestamp(currentTimestamp), '', duration.toString()];
                chunkConvertedData.push(convertedRow.map(cell => `"${cell}"`).join(', '));
                currentTimestamp = subtractDuration(currentTimestamp, duration);
                successCount++;
              }
            }

            convertedData = convertedData.concat(chunkConvertedData);
            processedRows = chunkEnd;

            // Yield control back to the event loop
            await new Promise(resolve => setTimeout(resolve, 0));
        }
    }

    return { convertedData: convertedData.join('\n'), successCount };
}

async function searchArtist(track, album) {
    const url = `https://itunes.apple.com/search?term=${encodeURIComponent(track)}+${encodeURIComponent(album)}&entity=song&limit=1`;
    const response = await fetch(url);
    const data = await response.json();

    if (data.resultCount > 0) {
        return data.results[0].artistName;
    } else {
        throw new Error('Artist not found');
    }
}

function formatTimestamp(timestamp) {
    return timestamp.toISOString().replace('T', ' ').substring(0, 19);
}

function subtractDuration(timestamp, duration) {
    return new Date(timestamp.getTime() - duration * 1000);
}

function displayOutput(convertedData) {
    outputText.value = convertedData;
    resultMessage.textContent = convertedData ? `Conversion complete. ${convertedData.split('\n').length} tracks processed.` : 'No data to display.';

    if (convertedData) {
        const rows = convertedData.split('\n');
        const initialRows = rows.slice(0, 15);
        const remainingRows = rows.slice(15);

        csvTableBody.innerHTML = '';
        initialRows.forEach((row, index) => {
          const cells = row.split(/,(?=(?:(?:[^"]*"){2})*[^"]*$)/);
          const newRow = csvTableBody.insertRow();
          cells.forEach((text, cellIndex) => {
            const cell = newRow.insertCell();
            cell.textContent = text.trim().replace(/^"|"$/g, '');

            // Bold the column with red for missing required data
            if ((cellIndex === 0 || cellIndex === 1) && cell.textContent === '') {
              cell.style.color = 'red';
              cell.style.fontWeight = 'bold';
              cell.setAttribute('data-tooltip', 'Empty fields!');
            }
          });
          newRow.style.opacity = 1 - (index / initialRows.length);
        });
      } else {
        csvTableBody.innerHTML = '';
      }

    // Remove the expand button
    const expandButton = document.querySelector('#expand-container button');
    if (expandButton) {
        expandButton.remove();
    }
}

function copyToClipboard() {
    outputText.select();
    document.execCommand('copy');
}

const saveButton = document.getElementById('save-button');
saveButton.addEventListener('click', saveAsCSV);

function saveAsCSV() {
    const csvData = outputText.value;
    const selectedRadio = document.querySelector('input[name="file-type"]:checked');
    let fileType = '';

    if (selectedRadio) {
        switch (selectedRadio.value) {
            case 'play-history':
                fileType = 'Play_History';
                break;
            case 'recently-played':
                fileType = 'Recently_Played';
                break;
            case 'play-activity':
                fileType = 'Play_Activity';
                break;
            default:
                fileType = 'Converted';
        }
    } else {
        fileType = 'Converted';
    }

    const blob = new Blob([csvData], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `${fileType}_Data.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
