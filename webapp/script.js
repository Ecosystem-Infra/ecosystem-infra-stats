'use strict';

const GITHUB_GREEN = '#2CBE4E'; // color of the "Changes approved" checkmark
const CHROME_BLUE = '#4285F4'; // https://github.com/alrra/browser-logos/blob/master/src/chrome/chrome.svg (also the Google blue)
const FIREFOX_ORANGE = '#E66000'; // https://www.mozilla.org/en-US/styleguide/identity/firefox/color/
const FIREFOX_YELLOW = '#FFCB00'; // ditto
const WEBKIT_PURPLE = '#8E56B1'; // https://github.com/w3c/web-platform-tests/pull/8986#issuecomment-356979677

function colorFromHeader(header) {
  if (header.includes('Chromium'))
    return CHROME_BLUE;
  if (header.includes('Gecko'))
    return FIREFOX_ORANGE;
  if (header.includes('Servo'))
    return FIREFOX_YELLOW;
  if (header.includes('WebKit'))
    return WEBKIT_PURPLE;
  return 'gray';
}

function colorFromIndex(index) {
  const palette = ['#e9c00a', '#af1315', '#0873dd', '#04a35b', '#e26f1d'];
  return palette[index % palette.length];
}

function parseCSV(csv) {
  const lines = csv.match(/[^\r\n]+/g);
  const rows = lines.map(line => line.split(','));
  const table = {
    headers: rows[0],
    rows: rows.slice(1),
  };

  if (table.headers.length == 0)
    throw new Error('no header line found');

  if (!table.rows.every(row => row.length == table.headers.length))
    throw new Error('rows of varying length');

  return table;
}

function configDataPoint(label, color, data) {
  return {
    label: label,
    data: data,
    lineTension: 0,
    borderColor: color,
    pointRadius: 0,
    pointHitRadius: 10,
    //backgroundColor: 'rgb(100, 200, 30, 0.9)',
  }
}

function drawChart(canvas, title, data) {
  new Chart(canvas, {
    type: 'line',
    data: data,
    options: {
      title: {
        display: true,
        fontSize: 18,
        text: [title],
      },
      legend: {
        reverse: true,
      },
      scales: {
        yAxes: [{
          ticks: { beginAtZero: true },
        }],
      },
    },
  });
}

fetch('wpt-commits.csv')
  .then(response => response.text())
  .then(text => {
    const table = parseCSV(text);
    // Drop the end of the data set (current month).
    table.rows = table.rows.slice(0, table.rows.length - 1);

    const data = {
      labels: table.rows.map(row => row[0]),
      datasets: [],
    };

    for (let i = 1; i < table.headers.length; i++) {
      const header = table.headers[i];
      const color = colorFromHeader(header);
      data.datasets.push(configDataPoint(header, color,
            table.rows.map(row => +row[i])));
    }

    data.datasets.reverse();
    drawChart(
        document.querySelector('#wpt-commits canvas'),
        'web-platform-tests commits',
        data);
  });

fetch('import-latency-stats.csv')
  .then(response => response.text())
  .then(text => {
    const table = parseCSV(text);
    // Drop the end of the data set (current month).
    table.rows = table.rows.slice(0, table.rows.length - 1);

    const data = {
      labels: table.rows.map(row => row[0]),
      datasets: [],
    };

    // 50%, 90%, Mean
    for (let i = 2; i <= 4; i++) {
      const header = table.headers[i];
      const color = colorFromIndex(i);
      data.datasets.push(configDataPoint(header, color,
            table.rows.map(row => +row[i])));
    }

    data.datasets.reverse();
    drawChart(
        document.querySelector('#wpt-imports canvas'),
        'WPT => Chromium import latency',
        data);
  });

fetch('export-latency-stats.csv')
  .then(response => response.text())
  .then(text => {
    const table = parseCSV(text);
    // Drop the first couple months when we didn't have stable exports;
    // drop the end of the data set (current month).
    table.rows = table.rows.slice(4, table.rows.length - 1);

    const data = {
      labels: table.rows.map(row => row[0]),
      datasets: [],
    };

    // 50%, 90%, Mean
    for (let i = 2; i <= 4; i++) {
      const header = table.headers[i];
      const color = colorFromIndex(i);
      data.datasets.push(configDataPoint(header, color,
            table.rows.map(row => +row[i])));
    }

    data.datasets.reverse();
    drawChart(
        document.querySelector('#wpt-exports canvas'),
        'Chromium => WPT export latency',
        data);
  });