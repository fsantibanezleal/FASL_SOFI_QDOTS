/**
 * Canvas-based image renderer with colormap support.
 *
 * Renders floating-point image data onto HTML canvas elements
 * with selectable colormaps (grayscale, hot, viridis).
 */

class ImageRenderer {
    constructor() {
        this.colormap = 'hot';
        this._colormaps = {
            grayscale: this._generateGrayscale(),
            hot: this._generateHot(),
            viridis: this._generateViridis(),
        };
    }

    /**
     * Render a float32 image (base64 encoded) to a canvas element.
     *
     * @param {string} canvasId - ID of the canvas element.
     * @param {string} base64Data - Base64-encoded float32 pixel data.
     * @param {number} width - Image width in pixels.
     * @param {number} height - Image height in pixels.
     */
    renderToCanvas(canvasId, base64Data, width, height) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');

        // Decode base64 to float32 array
        const binary = atob(base64Data);
        const bytes = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            bytes[i] = binary.charCodeAt(i);
        }
        const floatData = new Float32Array(bytes.buffer);

        // Create ImageData
        const imageData = ctx.createImageData(width, height);
        const cmap = this._colormaps[this.colormap] || this._colormaps.hot;

        for (let i = 0; i < floatData.length; i++) {
            let val = Math.max(0, Math.min(1, floatData[i]));
            const idx = Math.floor(val * 255);
            const pixel = i * 4;
            imageData.data[pixel] = cmap[idx][0];
            imageData.data[pixel + 1] = cmap[idx][1];
            imageData.data[pixel + 2] = cmap[idx][2];
            imageData.data[pixel + 3] = 255;
        }

        ctx.putImageData(imageData, 0, 0);
    }

    /**
     * Set the active colormap.
     * @param {string} name - Colormap name ('grayscale', 'hot', 'viridis').
     */
    setColormap(name) {
        if (this._colormaps[name]) {
            this.colormap = name;
        }
    }

    /**
     * Generate grayscale colormap (256 entries).
     */
    _generateGrayscale() {
        const cmap = [];
        for (let i = 0; i < 256; i++) {
            cmap.push([i, i, i]);
        }
        return cmap;
    }

    /**
     * Generate "hot" colormap (black -> red -> yellow -> white).
     */
    _generateHot() {
        const cmap = [];
        for (let i = 0; i < 256; i++) {
            const t = i / 255;
            let r, g, b;
            if (t < 0.33) {
                r = Math.floor(t / 0.33 * 255);
                g = 0;
                b = 0;
            } else if (t < 0.66) {
                r = 255;
                g = Math.floor((t - 0.33) / 0.33 * 255);
                b = 0;
            } else {
                r = 255;
                g = 255;
                b = Math.floor((t - 0.66) / 0.34 * 255);
            }
            cmap.push([Math.min(r, 255), Math.min(g, 255), Math.min(b, 255)]);
        }
        return cmap;
    }

    /**
     * Generate approximate "viridis" colormap.
     * Uses key color stops interpolated linearly.
     */
    _generateViridis() {
        const stops = [
            [0.0, 68, 1, 84],
            [0.13, 71, 44, 122],
            [0.25, 59, 81, 139],
            [0.38, 44, 113, 142],
            [0.50, 33, 144, 140],
            [0.63, 39, 173, 129],
            [0.75, 92, 200, 99],
            [0.88, 170, 220, 50],
            [1.0, 253, 231, 37],
        ];

        const cmap = [];
        for (let i = 0; i < 256; i++) {
            const t = i / 255;
            // Find surrounding stops
            let lower = stops[0], upper = stops[stops.length - 1];
            for (let s = 0; s < stops.length - 1; s++) {
                if (t >= stops[s][0] && t <= stops[s + 1][0]) {
                    lower = stops[s];
                    upper = stops[s + 1];
                    break;
                }
            }
            const frac = (upper[0] - lower[0]) > 0
                ? (t - lower[0]) / (upper[0] - lower[0])
                : 0;
            const r = Math.round(lower[1] + frac * (upper[1] - lower[1]));
            const g = Math.round(lower[2] + frac * (upper[2] - lower[2]));
            const b = Math.round(lower[3] + frac * (upper[3] - lower[3]));
            cmap.push([r, g, b]);
        }
        return cmap;
    }
}

// Export singleton
window.renderer = new ImageRenderer();
