<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip } from "chart.js";

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale, Filler, Tooltip);

const props = defineProps({
  label: { type: String, required: true },
  color: { type: String, required: true },
  simulated: { type: Boolean, default: false },
  points: { type: Array, required: true },
});

const canvas = ref(null);
let chart;

function labelsOf(points) {
  return points.map((point) =>
    new Date(point.ts * 1000).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
  );
}

function chartConfig(points) {
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
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: "#93a4b8", maxTicksLimit: 4 } },
        y: { ticks: { color: "#93a4b8" } },
      },
    },
  };
}

async function syncChart(points) {
  if (!points.length) {
    chart?.destroy();
    chart = undefined;
    return;
  }
  await nextTick();
  if (!canvas.value) return;
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
  <section class="panel">
    <h2>
      {{ label }}
      <span v-if="simulated" class="badge">simulé</span>
    </h2>
    <p v-if="points.length === 0" class="muted waiting">En attente de la carte ESP32</p>
    <canvas v-else ref="canvas"></canvas>
  </section>
</template>
