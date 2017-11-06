'use strict';

const GITHUB_GREEN = '#2CBE4E'; // color of the "Changes approved" checkmark
const CHROME_BLUE = '#4285F4'; // https://github.com/alrra/browser-logos/blob/master/src/chrome/chrome.svg (also the Google blue)
const FIREFOX_ORANGE = '#E66000'; // https://www.mozilla.org/en-US/styleguide/identity/firefox/color/
const FIREFOX_YELLOW = '#FFCB00'; // ditto

function colorFromHeader(header) {
  if (header.includes('Chromium'))
    return CHROME_BLUE;
  if (header.includes('Gecko'))
    return FIREFOX_ORANGE;
  if (header.includes('Servo'))
    return FIREFOX_YELLOW;
  return 'gray';
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

fetch('wpt-commits.csv')
  .then(response => response.text())
  .then(text => {
    const table = parseCSV(text);
    // drop the end of the data set (the future). TODO: automatic
    table.rows = table.rows.slice(0, table.rows.length - 2);

    const data = {
      labels: table.rows.map(row => row[0]),
      datasets: [],
    };

    for (let i = 1; i < table.headers.length; i++) {
      const header = table.headers[i];
      const color = colorFromHeader(header);
      data.datasets.push({
        label: header,
        data: table.rows.map(row => +row[i]),
        lineTension: 0,
        borderColor: color,
        pointRadius: 0,
        pointHitRadius: 10,
        //backgroundColor: 'rgb(100, 200, 30, 0.9)',
      });
    }

    data.datasets.reverse();

    new Chart(document.querySelector('#wpt-commits canvas'), {
      type: 'line',
      data: data,
      options: {
        title: {
          display: true,
          fontSize: 18,
          text: ['web-platform-tests commits'],
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
  });

const wptCommitData = {
  labels: [
    'GitHub PR',
    'Chromium export',
    'Gecko export',
    'Servo export',
  ],
  datasets: [{
    data: [395-80-52-57, 80, 52, 57],
    backgroundColor: [
      GITHUB_GREEN,
      CHROME_BLUE,
      FIREFOX_ORANGE,
      FIREFOX_YELLOW,
    ]
  }],
};

new Chart(document.querySelector('#wpt-commits-30d canvas'), {
  type: 'doughnut',
  data: wptCommitData,
  options: {
    title: {
      fontSize: 18,
      display: true,
      text: ['web-platform-tests commit origin (last 30 days)'],
    },
    legend: {
      display: true,
      position: 'right',
    },
  },
});
