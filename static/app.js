const state = {
  engines: [],
  customVoices: [],
  activeJob: null,
  pollTimer: null,
};

const elements = {
  script: document.querySelector("#script"),
  characterCount: document.querySelector("#character-count"),
  wordCount: document.querySelector("#word-count"),
  useSample: document.querySelector("#use-sample"),
  form: document.querySelector("#generation-form"),
  engine: document.querySelector("#engine"),
  engineNote: document.querySelector("#engine-note"),
  language: document.querySelector("#language"),
  languageNote: document.querySelector("#language-note"),
  voice: document.querySelector("#voice"),
  speed: document.querySelector("#speed"),
  speedValue: document.querySelector("#speed-value"),
  generate: document.querySelector("#generate"),
  machineStatus: document.querySelector("#machine-status"),
  progressFill: document.querySelector("#progress-fill"),
  transportState: document.querySelector("#transport-state"),
  outputMessage: document.querySelector("#output-message"),
  translationResult: document.querySelector("#translation-result"),
  translatedText: document.querySelector("#translated-text"),
  audioPlayer: document.querySelector("#audio-player"),
  cancelJob: document.querySelector("#cancel-job"),
  downloadLink: document.querySelector("#download-link"),
  voiceForm: document.querySelector("#voice-form"),
  voiceFeedback: document.querySelector("#voice-feedback"),
  savedVoices: document.querySelector("#saved-voices"),
  historyList: document.querySelector("#history-list"),
  refreshHistory: document.querySelector("#refresh-history"),
};

async function request(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const body = await response.json();
      message = body.detail || message;
    } catch {
      // Keep the status-based message when the server did not return JSON.
    }
    throw new Error(message);
  }
  if (response.status === 204) return null;
  return response.json();
}

function updateCounts() {
  const text = elements.script.value;
  const trimmed = text.trim();
  const words = !trimmed
    ? 0
    : "Segmenter" in Intl
      ? [...new Intl.Segmenter(undefined, { granularity: "word" }).segment(trimmed)].filter(
          (part) => part.isWordLike,
        ).length
      : trimmed.split(/\s+/u).length;
  const characters = [...text].length;
  elements.characterCount.textContent = `${characters.toLocaleString()} / 20,000`;
  elements.wordCount.textContent = `${words.toLocaleString()} ${words === 1 ? "word" : "words"}`;
}

function selectedEngine() {
  return state.engines.find((engine) => engine.id === elements.engine.value);
}

function updateEngineControls() {
  const engine = selectedEngine();
  if (!engine) return;

  elements.engineNote.textContent = engine.available
    ? engine.description
    : engine.availability_note;

  elements.language.replaceChildren(
    ...engine.languages.map((language) => new Option(languageLabel(language), language)),
  );

  updateVoiceControls();
}

function updateVoiceControls() {
  const engine = selectedEngine();
  if (!engine) return;

  const language = elements.language.value;
  const isEnglish = language === "en" || language === "en-gb";
  elements.languageNote.textContent = isEnglish
    ? "No translation. Your English text is read as written."
    : `English text is translated locally into ${languageLabel(language)} before speech.`;

  const builtInVoices = engine.voices
    .filter((voice) => voice.language === language || voice.language === "multi")
    .map((voice) => new Option(voice.name, voice.id));
  const clonedVoices = engine.supports_cloning
    ? state.customVoices.map((voice) => new Option(`${voice.name}, cloned`, voice.id))
    : [];
  elements.voice.replaceChildren(...builtInVoices, ...clonedVoices);
  elements.generate.disabled = !engine.available || elements.voice.options.length === 0;
}

function languageLabel(code) {
  const labels = {
    en: "English",
    "en-gb": "English, UK",
    hi: "Hindi",
    es: "Spanish",
    fr: "French",
    de: "German",
    it: "Italian",
    pt: "Portuguese",
    "pt-br": "Portuguese, Brazil",
    ja: "Japanese",
    zh: "Chinese",
    ar: "Arabic",
    ko: "Korean",
  };
  return labels[code] || code.toUpperCase();
}

async function loadSystem() {
  try {
    const system = await request("/api/system");
    const nvidia = system.nvidia;
    elements.machineStatus.className = `machine-status ${nvidia.ready ? "ready" : "warning"}`;
    elements.machineStatus.lastElementChild.textContent = nvidia.ready
      ? `${nvidia.name} ready`
      : `${nvidia.name}, setup needed`;
    elements.machineStatus.title = nvidia.detail;
  } catch (error) {
    elements.machineStatus.className = "machine-status warning";
    elements.machineStatus.lastElementChild.textContent = "Hardware check failed";
    elements.machineStatus.title = error.message;
  }
}

async function loadEngines() {
  state.engines = await request("/api/engines");
  const sorted = [...state.engines].sort((left, right) => Number(right.available) - Number(left.available));
  elements.engine.replaceChildren(
    ...sorted.map(
      (engine) => new Option(
        `${engine.name}${engine.available ? "" : " · install required"}`,
        engine.id,
        false,
        engine.id === "kokoro" && engine.available,
      ),
    ),
  );
  if (!selectedEngine()?.available) {
    const firstAvailable = sorted.find((engine) => engine.available);
    if (firstAvailable) elements.engine.value = firstAvailable.id;
  }
  updateEngineControls();
}

async function loadVoices() {
  state.customVoices = await request("/api/voices");
  renderSavedVoices();
  updateEngineControls();
}

function renderSavedVoices() {
  elements.savedVoices.hidden = state.customVoices.length === 0;
  elements.savedVoices.replaceChildren(
    ...state.customVoices.map((voice) => {
      const item = document.createElement("li");
      const name = document.createElement("span");
      const remove = document.createElement("button");
      name.textContent = voice.name;
      remove.type = "button";
      remove.className = "danger-action";
      remove.dataset.voiceId = voice.id;
      remove.textContent = "Delete";
      remove.setAttribute("aria-label", `Delete saved voice ${voice.name}`);
      item.append(name, remove);
      return item;
    }),
  );
}

function setOutput(status, message, progress = 0) {
  elements.transportState.textContent = status;
  elements.outputMessage.textContent = message;
  elements.progressFill.style.width = `${progress}%`;
}

function resetAudio() {
  elements.audioPlayer.pause();
  elements.audioPlayer.hidden = true;
  elements.audioPlayer.removeAttribute("src");
  elements.downloadLink.hidden = true;
  elements.downloadLink.removeAttribute("href");
  elements.cancelJob.hidden = true;
  elements.translationResult.hidden = true;
  elements.translationResult.open = false;
  elements.translatedText.textContent = "";
}

async function submitGeneration(event) {
  event.preventDefault();
  const text = elements.script.value.trim();
  if (!text) {
    elements.script.focus();
    setOutput("Script needed", "Enter some text before generating speech.", 0);
    return;
  }
  if ([...text].length > 20_000) {
    elements.script.focus();
    setOutput("Script too long", "Shorten the script to 20,000 characters or fewer.", 0);
    return;
  }

  resetAudio();
  elements.generate.disabled = true;
  setOutput("Sending to local model", "The job is entering the local generation queue.", 2);
  const outputFormat = new FormData(elements.form).get("format");

  try {
    const job = await request("/api/synthesize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        engine: elements.engine.value,
        voice_id: elements.voice.value,
        language: elements.language.value,
        speed: Number(elements.speed.value),
        output_format: outputFormat,
      }),
    });
    state.activeJob = job.id;
    elements.cancelJob.hidden = false;
    watchJob(job.id);
  } catch (error) {
    setOutput("Generation failed", error.message, 0);
    elements.generate.disabled = !selectedEngine()?.available;
  }
}

async function watchJob(jobId) {
  window.clearTimeout(state.pollTimer);
  try {
    const job = await request(`/api/jobs/${jobId}`);
    if (job.status === "complete") {
      state.activeJob = null;
      elements.cancelJob.hidden = true;
      setOutput("Audio ready", `Generated in ${job.generation_seconds.toFixed(2)} seconds.`, 100);
      if (job.translated_text) {
        elements.translatedText.textContent = job.translated_text;
        elements.translationResult.hidden = false;
        elements.translationResult.open = true;
      }
      elements.audioPlayer.src = job.audio_url;
      elements.audioPlayer.hidden = false;
      elements.downloadLink.href = job.audio_url;
      elements.downloadLink.hidden = false;
      elements.generate.disabled = !selectedEngine()?.available;
      await loadHistory();
      return;
    }
    if (job.status === "failed" || job.status === "cancelled") {
      state.activeJob = null;
      elements.cancelJob.hidden = true;
      setOutput("Generation failed", job.error || "The local model stopped.", job.progress);
      elements.generate.disabled = !selectedEngine()?.available;
      await loadHistory();
      return;
    }
    const translating = !["en", "en-gb"].includes(job.language) && job.progress < 35;
    elements.cancelJob.hidden = job.status !== "queued";
    const status =
      job.status === "queued"
        ? "Waiting for GPU"
        : translating
          ? "Translating locally"
          : "Generating speech";
    const message = translating
      ? `Converting the English script into ${languageLabel(job.language)}.`
      : `${job.engine} is processing this script.`;
    setOutput(status, message, job.progress);
    state.pollTimer = window.setTimeout(() => watchJob(jobId), 500);
  } catch (error) {
    setOutput("Status check failed", error.message, 0);
    elements.generate.disabled = !selectedEngine()?.available;
  }
}

async function saveVoice(event) {
  event.preventDefault();
  elements.voiceFeedback.classList.remove("error");
  elements.voiceFeedback.textContent = "Saving the reference recording locally...";
  try {
    const body = new FormData(elements.voiceForm);
    await request("/api/voices", { method: "POST", body });
    elements.voiceForm.reset();
    elements.voiceFeedback.textContent = "Voice saved. Select Chatterbox to use it.";
    await loadVoices();
  } catch (error) {
    elements.voiceFeedback.classList.add("error");
    elements.voiceFeedback.textContent = error.message;
  }
}

async function deleteVoice(event) {
  const button = event.target.closest("button[data-voice-id]");
  if (!button) return;
  const voice = state.customVoices.find((item) => item.id === button.dataset.voiceId);
  if (!voice || !window.confirm(`Delete the saved voice "${voice.name}" from this computer?`)) {
    return;
  }

  button.disabled = true;
  try {
    await request(`/api/voices/${voice.id}`, { method: "DELETE" });
    elements.voiceFeedback.classList.remove("error");
    elements.voiceFeedback.textContent = `Deleted ${voice.name}.`;
    await loadVoices();
  } catch (error) {
    button.disabled = false;
    elements.voiceFeedback.classList.add("error");
    elements.voiceFeedback.textContent = error.message;
  }
}

async function cancelActiveJob() {
  if (!state.activeJob) return;
  elements.cancelJob.disabled = true;
  try {
    await request(`/api/jobs/${state.activeJob}`, { method: "DELETE" });
    state.activeJob = null;
    elements.cancelJob.hidden = true;
    setOutput("Generation cancelled", "The queued job was removed.", 0);
    elements.generate.disabled = !selectedEngine()?.available;
    await loadHistory();
  } catch (error) {
    elements.cancelJob.hidden = true;
    setOutput("Could not cancel", error.message, 0);
  } finally {
    elements.cancelJob.disabled = false;
  }
}

async function loadHistory() {
  const jobs = await request("/api/history");
  if (!jobs.length) {
    elements.historyList.innerHTML = '<li class="empty-history">No generated files yet.</li>';
    return;
  }
  elements.historyList.replaceChildren(
    ...jobs.slice(0, 10).map((job) => {
      const item = document.createElement("li");
      const summary = document.createElement("div");
      const title = document.createElement("p");
      const metadata = document.createElement("span");
      title.className = "history-title";
      title.textContent = job.status === "complete" ? `${job.engine} audio` : `${job.engine} · ${job.status}`;
      metadata.className = "history-meta";
      metadata.textContent = `${new Date(job.created_at).toLocaleString()} · ${job.output_format.toUpperCase()}`;
      summary.append(title, metadata);
      item.append(summary);
      if (job.audio_url) {
        const link = document.createElement("a");
        link.href = job.audio_url;
        link.textContent = "Download";
        link.download = "";
        item.append(link);
      }
      return item;
    }),
  );
}

elements.script.addEventListener("input", updateCounts);
elements.useSample.addEventListener("click", () => {
  elements.script.value =
    "This is a private text-to-speech test running on my computer. The voice model works without sending this paragraph to a cloud service.";
  updateCounts();
  elements.script.focus();
});
elements.engine.addEventListener("change", updateEngineControls);
elements.language.addEventListener("change", updateVoiceControls);
elements.speed.addEventListener("input", () => {
  elements.speedValue.textContent = `${Number(elements.speed.value).toFixed(2)}×`;
});
elements.form.addEventListener("submit", submitGeneration);
elements.voiceForm.addEventListener("submit", saveVoice);
elements.savedVoices.addEventListener("click", deleteVoice);
elements.cancelJob.addEventListener("click", cancelActiveJob);
elements.refreshHistory.addEventListener("click", loadHistory);

Promise.all([loadSystem(), loadVoices()])
  .then(loadEngines)
  .then(loadHistory)
  .catch((error) => setOutput("Studio failed to load", error.message, 0));

updateCounts();
