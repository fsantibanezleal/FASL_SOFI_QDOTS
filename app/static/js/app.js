/**
 * FASL SOFI QDOTS - Main Application Controller.
 *
 * Manages UI state, API calls, and image rendering for the
 * SOFI processing web application.
 */

document.addEventListener('DOMContentLoaded', () => {
    // --- State ---
    let hasData = false;
    let currentResults = {};

    // --- DOM Elements ---
    const btnSimulate = document.getElementById('btn-simulate');
    const btnProcess = document.getElementById('btn-process');
    const btnHelp = document.getElementById('btn-help');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    const imageGrid = document.getElementById('image-grid');
    const logArea = document.getElementById('log-area');
    const statusDot = document.getElementById('status-dot');
    const modalOverlay = document.getElementById('modal-overlay');
    const modalClose = document.getElementById('modal-close');

    // --- Colormap buttons ---
    document.querySelectorAll('.colormap-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.colormap-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            window.renderer.setColormap(btn.dataset.cmap);
            rerenderAll();
        });
    });

    // --- WebSocket ---
    window.sofiWS.onMessage((msg) => {
        if (msg.type === 'connection') {
            statusDot.classList.toggle('disconnected', !msg.connected);
        } else if (msg.type === 'progress') {
            showProgress(msg.step, msg.progress);
        }
    });
    window.sofiWS.connect();

    // Periodic ping
    setInterval(() => window.sofiWS.ping(), 30000);

    // --- Log ---
    function log(message, level = 'info') {
        const entry = document.createElement('div');
        entry.className = `log-entry ${level}`;
        const time = new Date().toLocaleTimeString();
        entry.textContent = `[${time}] ${message}`;
        logArea.appendChild(entry);
        logArea.scrollTop = logArea.scrollHeight;
    }

    // --- Progress ---
    function showProgress(step, fraction) {
        progressContainer.classList.add('active');
        progressBar.style.width = `${Math.round(fraction * 100)}%`;
        progressText.textContent = step;
        if (fraction >= 1.0) {
            setTimeout(() => {
                progressContainer.classList.remove('active');
            }, 1500);
        }
    }

    // --- Simulate ---
    btnSimulate.addEventListener('click', async () => {
        btnSimulate.disabled = true;
        btnProcess.disabled = true;
        log('Starting simulation...');

        const params = {
            num_frames: parseInt(document.getElementById('num-frames').value) || 500,
            image_size: parseInt(document.getElementById('image-size').value) || 64,
            num_emitters: parseInt(document.getElementById('num-emitters').value) || 20,
            psf_sigma: parseFloat(document.getElementById('psf-sigma').value) || 2.0,
            brightness: parseFloat(document.getElementById('brightness').value) || 1000,
            background: parseFloat(document.getElementById('background').value) || 100,
            noise_std: parseFloat(document.getElementById('noise-std').value) || 20,
            seed: document.getElementById('seed').value ? parseInt(document.getElementById('seed').value) : null,
        };

        try {
            const resp = await fetch('/api/simulate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params),
            });
            const data = await resp.json();

            if (data.status === 'ok') {
                hasData = true;
                log(`Simulation complete: ${data.num_frames} frames, ${data.num_emitters} emitters, ${data.elapsed_seconds}s`, 'success');

                // Render mean image
                renderImageCard('mean', 'Mean Image (Widefield)', data.mean_image, data.mean_shape[1], data.mean_shape[0]);
                currentResults['mean'] = { image: data.mean_image, shape: data.mean_shape };
            } else {
                log('Simulation failed', 'error');
            }
        } catch (e) {
            log(`Error: ${e.message}`, 'error');
        }

        btnSimulate.disabled = false;
        btnProcess.disabled = !hasData;
    });

    // --- Process ---
    btnProcess.addEventListener('click', async () => {
        if (!hasData) return;

        btnProcess.disabled = true;
        btnSimulate.disabled = true;
        log('Starting SOFI processing...');

        // Gather selected orders
        const orders = [];
        document.querySelectorAll('.order-checkbox:checked').forEach(cb => {
            orders.push(parseInt(cb.value));
        });

        if (orders.length === 0) {
            log('No orders selected', 'error');
            btnProcess.disabled = false;
            btnSimulate.disabled = false;
            return;
        }

        const params = {
            orders: orders,
            window_size: parseInt(document.getElementById('window-size').value) || 100,
            use_fourier: document.getElementById('use-fourier').checked,
            deconvolution: document.getElementById('deconv-method').value,
            linearize: document.getElementById('linearize').checked,
            psf_sigma: parseFloat(document.getElementById('psf-sigma').value) || 2.0,
        };

        try {
            const resp = await fetch('/api/process', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(params),
            });
            const data = await resp.json();

            if (data.status === 'ok') {
                log(`Processing complete: orders ${data.orders.join(', ')}, ${data.elapsed_seconds}s`, 'success');

                for (const order of data.orders) {
                    const r = data.results[String(order)];
                    const label = `SOFI Order ${order} (${Math.sqrt(order).toFixed(2)}x)`;
                    renderImageCard(`sofi-${order}`, label, r.image, r.shape[1], r.shape[0]);
                    currentResults[`sofi-${order}`] = { image: r.image, shape: r.shape };
                }
            } else {
                log('Processing failed', 'error');
            }
        } catch (e) {
            log(`Error: ${e.message}`, 'error');
        }

        btnProcess.disabled = false;
        btnSimulate.disabled = false;
    });

    // --- Render image card ---
    function renderImageCard(id, title, base64Data, width, height) {
        let card = document.getElementById(`card-${id}`);
        if (!card) {
            card = document.createElement('div');
            card.className = 'image-card';
            card.id = `card-${id}`;
            card.innerHTML = `
                <div class="card-header">
                    <span>${title}</span>
                    <span class="badge">${width}x${height}</span>
                </div>
                <canvas id="canvas-${id}"></canvas>
                <div class="card-footer">${title}</div>
            `;
            // Remove empty state if present
            const empty = document.getElementById('empty-state');
            if (empty) empty.remove();
            imageGrid.appendChild(card);
        } else {
            card.querySelector('.card-header span:first-child').textContent = title;
            card.querySelector('.badge').textContent = `${width}x${height}`;
        }

        window.renderer.renderToCanvas(`canvas-${id}`, base64Data, width, height);
    }

    // --- Re-render all images with current colormap ---
    function rerenderAll() {
        for (const [id, data] of Object.entries(currentResults)) {
            window.renderer.renderToCanvas(
                `canvas-${id}`,
                data.image,
                data.shape[1] || data.shape[0],
                data.shape[0]
            );
        }
    }

    // --- Help modal ---
    btnHelp.addEventListener('click', () => {
        modalOverlay.classList.add('active');
    });

    modalClose.addEventListener('click', () => {
        modalOverlay.classList.remove('active');
    });

    modalOverlay.addEventListener('click', (e) => {
        if (e.target === modalOverlay) {
            modalOverlay.classList.remove('active');
        }
    });

    log('Application initialized. Click "Simulate" to generate data.');
});
