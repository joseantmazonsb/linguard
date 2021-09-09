Chart.defaults.font.family = '-apple-system,system-ui,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif';
Chart.defaults.color = '#292b2c';

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

    sortChartData(labels, values) {
        let objs = labels.map(function(d, i) {
          return {
            label: d,
            data: values[i] || 0
          };
        });

        let sortedArrayOfObj = objs.sort(function(a, b) {
          return b.data - a.data;
        });

        let newArrayLabel = [];
        let newArrayData = [];
        sortedArrayOfObj.forEach(function(d){
          newArrayLabel.push(d.label);
          newArrayData.push(d.data);
        });
        return {
            labels: newArrayLabel,
            values: newArrayData
        }
    }

    createBarChart(title, yValuesTag, canvasId, labels, values, dataLabel) {
        const colors = this.getRandomColorPalette(labels.length);
        const dct = this.sortChartData(labels, values);
        const data = {
          labels: dct.labels,
          datasets: [{
            label: dataLabel,
            data: dct.values,
            backgroundColor: colors,
            borderColor: colors,
          }],
        };

        const options = {
          scales: {
              y: {
                  ticks: {
                      callback: function(value, index, values) {
                          return value + yValuesTag;
                      }
                  },
              }
          },
          plugins: {
              title: {
                  display: title.length > 0,
                  text: title
              }
          }
        };
        return new Chart(document.getElementById(canvasId), {
            type: 'bar',
            data: data,
            options: options
        });
    }
}
let chartUtils = new ChartUtils();

if (typeof module === "object" && module.exports) {
  module.exports = chartUtils
}
