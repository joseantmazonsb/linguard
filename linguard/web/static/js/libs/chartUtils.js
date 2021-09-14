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

    filesizeCallback(value, max) {
        if (max > 1024*1024*1024*1024*1024) {
            return (value / 1024 / 1024 / 1024 / 1024 / 1024).toFixed(1) + " PB";
        }
        if (max > 1024*1024*1024*1024) {
            return (value/1024/1024/1024/1024).toFixed(1) + " TB";
        }
        if (max > 1024*1024*1024) {
            return (value/1024/1024/1024).toFixed(1) + " GB";
        }
        if (max > 1024*1024) {
            return (value/1024/1024).toFixed(1) + " MB";
        }
        if (max > 1024) {
            return (value / 1024).toFixed(1) + " KB";
        }
        return (value) + " B";
    }

    ticksFilesizeCallback(value, max) {
        return this.filesizeCallback(value, max);
    }

    tooltipFilesizeCallback(context) {
        let max = context.chart.scales.y.max;
        let value = context.dataset.data[context.dataIndex];
        return this.filesizeCallback(value, max);
    }
}
let chartUtils = new ChartUtils();

if (typeof module === "object" && module.exports) {
  module.exports = chartUtils
}
