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
}
let chartUtils = new ChartUtils();

if (typeof module === "object" && module.exports) {
  module.exports = chartUtils
}
