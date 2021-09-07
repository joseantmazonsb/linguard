Chart.defaults.font.family = '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.color = '#292b2c';
Chart.register(ChartDataLabels);

function getRandomInt(min, max) {
  return Math.floor(Math.random() * (max - min)) + min;
}

class ChartUtils {

    /**
     *
     * @param nColors Desired amount of colors for the palette.
     * @param schemeType mono, triade, tetrade, analogic
     * @param variation default, soft, pastel, light, hard, pale
     * @returns {[]}
     */
    getRandomColorPalette(nColors, schemeType = "triade", variation = "pastel") {
        const colors = [];
        let previousSeed = -1, seed = -1;
        const MAX_TRIES = 10;
        while (colors.length < nColors) {
            let tries = -1;
            while (tries < MAX_TRIES && previousSeed === seed) {
                seed = getRandomInt(0, 361);
            }
            let scheme = new ColorScheme;
            scheme.from_hue(seed)
                .scheme(schemeType)
                .variation(variation);
            for (let color of scheme.colors().slice(2)) {
                colors.push("#"+color);
            }
        }
        return colors;
    }

    createChart(canvasId, labels, values, dataLabel, config, colors = []) {
        if (!colors || colors.length < 1) {
            colors = this.getRandomColorPalette(labels.length);
        }
        const data = {
          labels: labels,
          datasets: [
            {
              label: 'Dataset',
              data: values,
              backgroundColor: colors,
              datalabels: {
                formatter: function(value, context) {
                  return context.chart.data.labels[context.dataIndex] + ": " + Number(context.dataset.data[context.dataIndex]).toFixed(3) + dataLabel;
                }
              }
            }
          ]
        };
        config["data"] = data
        return new Chart(document.getElementById(canvasId), config);
    }

    createDoughnoutChart(title, canvasId, labels, values, dataLabel, colorPalette = null) {
        const config = {
          type: 'doughnut',
          options: {
            responsive: true,
            plugins: {
              legend: {
                position: 'top',
              },
              title: {
                  display: title.length > 0,
                  text: title
              }
            }
          },
        };
        return this.createChart(canvasId, labels, values, dataLabel, config, colorPalette)
    }
}
let chartUtils = new ChartUtils();

if (typeof module === "object" && module.exports) {
  module.exports = chartUtils
}
