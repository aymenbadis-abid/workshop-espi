<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, Legend } from "chart.js";

const boardLimitsPlugin = {
  id: "boardLimits",
  afterDraw(chart) {
    const lines = chart.options.plugins?.boardLimits?.lines;
    if (!lines?.length) return;
    const { ctx, chartArea, scales } = chart;
    const yScale = scales.y;
    if (!chartArea || !yScale) return;
    for (const line of lines) {
      const y = yScale.getPixelForValue(line.value);
      if (y < chartArea.top || y > chartArea.bottom) continue;
      ctx.save();
      ctx.beginPath();
      ctx.strokeStyle = line.color;
      ctx.lineWidth = 1;
      ctx.setLineDash([5, 4]);
      ctx.moveTo(chartArea.left, y);
      ctx.lineTo(chartArea.right, y);
      ctx.stroke();
      ctx.fillStyle = line.color;
      ctx.font = "600 13px Segoe UI, sans-serif";
      const width = ctx.measureText(line.label).width;
      const textY = y - 14 < chartArea.top ? y + 14 : y - 6;
      ctx.fillText(line.label, chartArea.right - width - 6, textY);
      ctx.restore();
    }
  },
};

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip, Legend, boardLimitsPlugin);

const props = defineProps({
  label: { type: String, required: true },
  color: { type: String, required: true },
  state: { type: String, default: "" },
  points: { type: Array, required: true },
  limits: { type: Array, default: () => [] },
  limitCaption: { type: String, default: "" },
});

const canvas = ref(null);
let chart;
let chartGeneration = 0;

const latestClock = computed(() => {
  const point = props.points.at(-1);
  if (!point || !Number.isFinite(point.ts)) return "";
  return new Date(point.ts * 1000).toLocaleTimeString("fr-FR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
});

function labelsOf(points) {
  return points.map((point) =>
    new Date(point.ts * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  );
}

function chartConfig(points) {
  const limits = props.limits;
  return {
    type: "line",
    data: {
      labels: labelsOf(points),
      datasets: [
        {
          label: props.label,
          data: points.map((point) => point.value),
          borderColor: props.color,
          backgroundColor: props.color + "33",
          fill: true,
          tension: 0.25,
          pointRadius: 0,
        },
      ],
    },
    options: {
      animation: false,
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        boardLimits: { lines: limits },
      },
      scales: {
        x: {
          ticks: { color: "#93a4b8", maxTicksLimit: 4, autoSkip: true },
          afterBuildTicks(scale) {
            const ticks = scale.ticks;
            if (!ticks.length || scale.max == null) return;
            const last = ticks[ticks.length - 1];
            if (last.value === scale.max) return;
            ticks.push({ value: scale.max, label: scale.getLabelForValue(scale.max) });
          },
        },
        y: {
          bounds: "data",
          ticks: { color: "#93a4b8", stepSize: 2 },
          afterDataLimits(scale) {
            if (!limits.length) return;
            const top = Math.max(...limits.map((line) => line.value));
            const bottom = Math.min(...limits.map((line) => line.value));
            if (scale.max < top + 1) scale.max = top + 1;
            if (scale.min > bottom - 2) scale.min = bottom - 2;
          },
        },
      },
    },
  };
}

async function syncChart(points) {
  const generation = ++chartGeneration;
  if (!points.length) {
    chart?.destroy();
    chart = undefined;
    return;
  }
  await nextTick();
  if (generation !== chartGeneration || !canvas.value) return;
  if (!chart) {
    chart = new Chart(canvas.value, chartConfig(points));
    return;
  }
  chart.data.labels = labelsOf(points);
  chart.data.datasets[0].data = points.map((point) => point.value);
  chart.update("none");
}

onMounted(() => {
  syncChart(props.points);
});

watch(
  () => props.points,
  (points) => {
    syncChart(points);
  },
  { deep: true },
);

onBeforeUnmount(() => chart?.destroy());
</script>

<template>
  <section class="panel measure">
    <h2>
      {{ label }}
      <span v-if="state" class="badge" :class="state === 'réelle' ? 'real' : 'sim'">{{ state }}</span>
    </h2>
    <div class="readout">
      <template v-if="points.length">
        <slot />
        <p v-if="latestClock" class="muted">Mesure à {{ latestClock }}</p>
      </template>
    </div>
    <div class="plot">
      <canvas v-show="points.length" ref="canvas"></canvas>
      <p v-if="!points.length" class="muted waiting">En attente de la carte ESP32</p>
    </div>
    <p class="muted limit-caption">{{ limitCaption }}</p>
  </section>
</template>
