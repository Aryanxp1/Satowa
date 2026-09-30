/**
 * Interactive Background Boxes Ripple Effect for Setowa Showcase Hero.
 * Inspired by Aceternity UI, tailored for Setowa's warm heritage and dark forest color palette.
 * 
 * Features:
 * - Full-width interactive grid of boxes behind the Hero section
 * - Smooth cell illumination on hover
 * - Concentric ripple waves on click/tap with fluid decay physics
 * - Radial vignette fade at edges into the page background
 * - Cohesive with Setowa light/dark theme tokens
 * - Hardware-accelerated, performant (60 FPS) canvas engine
 */
(() => {
  function initRipple() {
    const container = document.getElementById('hero-area');
    const canvas = document.getElementById('hero-ripple-canvas');
    if (!container || !canvas) return;

    const ctx = canvas.getContext('2d');
    let width = 0;
    let height = 0;
    let dpr = 1;

    const CELL_SIZE = 46; // Size of each grid box in px
    const ripples = [];
    let mouse = { x: -1000, y: -1000, active: false };
    let isRunning = false;
    let animId = null;
    let lastTime = 0;
    let lastTouchTime = 0;

    // Track cell states: key "c,r" -> { hoverFactor, waveFactor }
    const cellStates = new Map();

    function getThemeColors() {
      const isDark = document.documentElement.dataset.theme === 'dark';
      if (isDark) {
        return {
          isDark: true,
          gridLine: 'rgba(186, 208, 171, 0.075)',
          gridLineHover: 'rgba(186, 208, 171, 0.28)',
          hoverFill: [186, 208, 171],      // sage green
          waveFill: [186, 208, 171],       // --green
          waveFillPastel: [169, 188, 140], // --pastel
          dotColor: 'rgba(186, 208, 171, 0.16)',
          dotActive: 'rgba(186, 208, 171, 0.45)'
        };
      } else {
        return {
          isDark: false,
          gridLine: 'rgba(67, 95, 72, 0.085)',
          gridLineHover: 'rgba(67, 95, 72, 0.32)',
          hoverFill: [139, 154, 110],      // warm pastel sage
          waveFill: [67, 95, 72],          // deep forest green
          waveFillPastel: [139, 154, 110], // sage
          dotColor: 'rgba(67, 95, 72, 0.14)',
          dotActive: 'rgba(67, 95, 72, 0.40)'
        };
      }
    }

    function resize() {
      const rect = container.getBoundingClientRect();
      width = Math.max(rect.width, 300);
      height = Math.max(rect.height, 200);
      dpr = Math.min(window.devicePixelRatio || 1, 2);

      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;

      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      requestRender();
    }

    function addRipple(x, y, intensity = 1.0) {
      const maxRadius = Math.hypot(Math.max(x, width - x), Math.max(y, height - y)) + 100;
      ripples.push({
        x,
        y,
        radius: 0,
        maxRadius,
        speed: 390, // px per second
        waveWidth: 120, // thickness of wave band
        age: 0,
        maxAge: 2.1, // duration in seconds
        intensity
      });
      startLoop();
    }

    function updateRipples(dt) {
      for (let i = ripples.length - 1; i >= 0; i--) {
        const r = ripples[i];
        r.age += dt;
        r.radius += r.speed * dt;
        if (r.age >= r.maxAge || r.radius >= r.maxRadius) {
          ripples.splice(i, 1);
        }
      }
    }

    function render(time) {
      if (!lastTime) lastTime = time;
      const dt = Math.min((time - lastTime) / 1000, 0.08);
      lastTime = time;

      updateRipples(dt);

      ctx.clearRect(0, 0, width, height);

      const colors = getThemeColors();
      const cols = Math.ceil(width / CELL_SIZE);
      const rows = Math.ceil(height / CELL_SIZE);

      const activeHoverC = mouse.active ? Math.floor(mouse.x / CELL_SIZE) : -1;
      const activeHoverR = mouse.active ? Math.floor(mouse.y / CELL_SIZE) : -1;

      let hasActiveEnergy = ripples.length > 0;

      for (let c = 0; c < cols; c++) {
        for (let r = 0; r < rows; r++) {
          const x = c * CELL_SIZE;
          const y = r * CELL_SIZE;
          const cx = x + CELL_SIZE / 2;
          const cy = y + CELL_SIZE / 2;

          const key = `${c},${r}`;
          let state = cellStates.get(key);
          if (!state) {
            state = { hoverFactor: 0, waveFactor: 0 };
            cellStates.set(key, state);
          }

          // Hover illumination calculation
          const isHovered = (c === activeHoverC && r === activeHoverR);
          const targetHover = isHovered ? 1.0 : 0;
          state.hoverFactor += (targetHover - state.hoverFactor) * Math.min(dt * 14, 1);

          // Ripple wave contribution
          let totalWave = 0;
          for (let i = 0; i < ripples.length; i++) {
            const rip = ripples[i];
            const dist = Math.hypot(cx - rip.x, cy - rip.y);
            const diff = Math.abs(dist - rip.radius);

            if (diff < rip.waveWidth) {
              const progress = rip.age / rip.maxAge;
              const decay = Math.pow(1 - progress, 1.7);
              const waveBell = Math.cos((diff / rip.waveWidth) * (Math.PI / 2));
              totalWave = Math.max(totalWave, waveBell * decay * rip.intensity);
            }
          }

          // Fast rise, gentle trailing decay for organic fluid feel
          const waveRate = totalWave > state.waveFactor ? 26 : 8.5;
          state.waveFactor += (totalWave - state.waveFactor) * Math.min(dt * waveRate, 1);

          if (state.hoverFactor > 0.008 || state.waveFactor > 0.008) {
            hasActiveEnergy = true;
          }

          // Combine hover & wave factors
          const combinedFactor = Math.min(1.0, state.hoverFactor * 0.75 + state.waveFactor);

          if (combinedFactor > 0.01) {
            // Illuminated cell fill
            const rgb = colors.isDark ? colors.waveFill : colors.waveFillPastel;
            const fillAlpha = (combinedFactor * (colors.isDark ? 0.22 : 0.17)).toFixed(3);
            ctx.fillStyle = `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${fillAlpha})`;
            ctx.fillRect(x + 1, y + 1, CELL_SIZE - 1, CELL_SIZE - 1);

            // Illuminated border
            const borderAlpha = (0.08 + combinedFactor * (colors.isDark ? 0.38 : 0.32)).toFixed(3);
            ctx.strokeStyle = `rgba(${rgb[0]}, ${rgb[1]}, ${rgb[2]}, ${borderAlpha})`;
            ctx.lineWidth = 1;
            ctx.strokeRect(x + 0.5, y + 0.5, CELL_SIZE, CELL_SIZE);
          } else {
            // Default ambient grid line
            ctx.strokeStyle = colors.gridLine;
            ctx.lineWidth = 1;
            ctx.strokeRect(x + 0.5, y + 0.5, CELL_SIZE, CELL_SIZE);
          }

          // Subtle intersection micro-markers
          if (c > 0 && r > 0 && (c + r) % 2 === 0) {
            ctx.fillStyle = combinedFactor > 0.15 ? colors.dotActive : colors.dotColor;
            ctx.fillRect(x - 1, y - 1, 2, 2);
          }
        }
      }

      if (hasActiveEnergy || mouse.active) {
        animId = requestAnimationFrame(render);
      } else {
        isRunning = false;
        animId = null;
        lastTime = 0;
      }
    }

    function startLoop() {
      if (!isRunning) {
        isRunning = true;
        lastTime = 0;
        animId = requestAnimationFrame(render);
      }
    }

    function requestRender() {
      startLoop();
    }

    // Pointer events on container
    container.addEventListener('mousemove', (e) => {
      const rect = container.getBoundingClientRect();
      mouse.x = e.clientX - rect.left;
      mouse.y = e.clientY - rect.top;
      mouse.active = true;
      startLoop();
    });

    container.addEventListener('mouseleave', () => {
      mouse.active = false;
    });

    // Touch support for mobile/tablet
    container.addEventListener('touchstart', (e) => {
      if (e.touches && e.touches[0]) {
        lastTouchTime = Date.now();
        const rect = container.getBoundingClientRect();
        const x = e.touches[0].clientX - rect.left;
        const y = e.touches[0].clientY - rect.top;
        addRipple(x, y, 1.0);
      }
    }, { passive: true });

    // Click handler for mouse & trackpad
    container.addEventListener('click', (e) => {
      // Prevent duplicate trigger if touchstart just fired
      if (Date.now() - lastTouchTime < 400) return;
      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      addRipple(x, y, 1.0);
    });

    // Window resize
    window.addEventListener('resize', resize, { passive: true });

    // Dynamic theme switching
    const observer = new MutationObserver(() => {
      requestRender();
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    // Initial setup
    resize();

    // Subtle initial ambient ripple on load
    setTimeout(() => {
      addRipple(width / 2, height / 2.2, 0.75);
    }, 400);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initRipple);
  } else {
    initRipple();
  }
})();
