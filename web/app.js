document.addEventListener("DOMContentLoaded", () => {
    // State
    let selectedVideoPath = null;
    let selectedVideoFolder = null;
    let ws = null;
    let totalDialogueCount = 0;

    // DOM Elements
    const dropZone = document.getElementById("dropZone");
    const btnBrowseVideo = document.getElementById("btnBrowseVideo");
    const fileInfoBox = document.getElementById("fileInfoBox");
    const selectedFileName = document.getElementById("selectedFileName");
    const selectedFilePath = document.getElementById("selectedFilePath");
    const selectedFileSize = document.getElementById("selectedFileSize");
    const btnClearFile = document.getElementById("btnClearFile");

    const chkSeparateBgm = document.getElementById("chkSeparateBgm");
    const selSourceLang = document.getElementById("selSourceLang");
    const selWhisperModel = document.getElementById("selWhisperModel");
    const rangeBgmVol = document.getElementById("rangeBgmVol");
    const valBgmVol = document.getElementById("valBgmVol");
    const rangeDubVol = document.getElementById("rangeDubVol");
    const valDubVol = document.getElementById("valDubVol");
    const rangeOrigVol = document.getElementById("rangeOrigVol");
    const valOrigVol = document.getElementById("valOrigVol");
    const chkBurnSubtitles = document.getElementById("chkBurnSubtitles");
    const chkSaveStems = document.getElementById("chkSaveStems");

    const btnStartProcess = document.getElementById("btnStartProcess");
    const btnCancelProcess = document.getElementById("btnCancelProcess");

    const progressBarFill = document.getElementById("progressBarFill");
    const lblProgressPct = document.getElementById("lblProgressPct");
    const currentStageDesc = document.getElementById("currentStageDesc");
    const systemStatusText = document.getElementById("systemStatusText");

    const resultCard = document.getElementById("resultCard");
    const resultVideoPlayer = document.getElementById("resultVideoPlayer");
    const resVideoPath = document.getElementById("resVideoPath");
    const resSrtPath = document.getElementById("resSrtPath");
    const btnOpenFolder = document.getElementById("btnOpenFolder");

    const dialogueStreamContainer = document.getElementById("dialogueStreamContainer");
    const dialogueCountTag = document.getElementById("dialogueCountTag");
    const consoleLogs = document.getElementById("consoleLogs");
    const btnClearLogs = document.getElementById("btnClearLogs");
    const audioPreviewPlayer = document.getElementById("audioPreviewPlayer");

    const voiceCards = document.querySelectorAll(".voice-card");

    // -------------------------------------------------------------
    // Slider Value Listeners
    // -------------------------------------------------------------
    rangeBgmVol.addEventListener("input", (e) => {
        valBgmVol.textContent = `${e.target.value}%`;
    });

    rangeDubVol.addEventListener("input", (e) => {
        valDubVol.textContent = `${e.target.value}%`;
    });

    rangeOrigVol.addEventListener("input", (e) => {
        const val = parseInt(e.target.value);
        valOrigVol.textContent = val === 0 ? "0% (Muted)" : `${val}%`;
    });

    // -------------------------------------------------------------
    // Voice Selection Card Handlers
    // -------------------------------------------------------------
    voiceCards.forEach(card => {
        card.addEventListener("click", () => {
            voiceCards.forEach(c => c.classList.remove("active"));
            card.classList.add("active");
            const radio = card.querySelector("input[type='radio']");
            if (radio) radio.checked = true;
        });
    });

    // Voice Audition / Preview Button
    document.querySelectorAll(".btn-preview-voice").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const voiceId = btn.getAttribute("data-voice");
            const origText = btn.innerHTML;
            btn.innerHTML = `កំពុងបង្កើត...`;
            btn.disabled = true;

            try {
                const res = await fetch("/api/preview-voice", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ voice_id: voiceId })
                });
                if (res.ok) {
                    const blob = await res.blob();
                    const audioUrl = URL.createObjectURL(blob);
                    audioPreviewPlayer.src = audioUrl;
                    audioPreviewPlayer.play();
                } else {
                    alert("មិនអាចបង្កើតសំឡេងសាកល្បងបានទេ។");
                }
            } catch (err) {
                console.error(err);
            } finally {
                btn.innerHTML = origText;
                btn.disabled = false;
            }
        });
    });

    // -------------------------------------------------------------
    // Video Selection via Native Windows File Dialog
    // -------------------------------------------------------------
    async function selectVideoFile() {
        try {
            const res = await fetch("/api/select-video", { method: "POST" });
            const data = await res.json();
            if (data.cancelled) return;
            if (data.error) {
                alert(`កំហុស: ${data.error}`);
                return;
            }

            setVideoFile(data.file_path, data.filename, data.size_mb, data.folder);
        } catch (err) {
            console.error("File selection error:", err);
        }
    }

    function setVideoFile(path, name, sizeMb, folder) {
        selectedVideoPath = path;
        selectedVideoFolder = folder;
        selectedFileName.textContent = name;
        selectedFilePath.textContent = path;
        selectedFileSize.textContent = `${sizeMb} MB`;

        dropZone.classList.add("hidden");
        fileInfoBox.classList.remove("hidden");
        logMessage(`[File] បានជ្រើសរើសវីដេអូ: ${name} (${sizeMb} MB)`);
    }

    btnBrowseVideo.addEventListener("click", selectVideoFile);
    dropZone.addEventListener("click", selectVideoFile);

    btnClearFile.addEventListener("click", () => {
        selectedVideoPath = null;
        selectedVideoFolder = null;
        dropZone.classList.remove("hidden");
        fileInfoBox.classList.add("hidden");
        resultCard.classList.add("hidden");
    });

    // Drag and Drop Effects
    dropZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZone.classList.add("dragover");
    });

    dropZone.addEventListener("dragleave", () => {
        dropZone.classList.remove("dragover");
    });

    dropZone.addEventListener("drop", (e) => {
        e.preventDefault();
        dropZone.classList.remove("dragover");
        // Drag-drop on browser window can trigger native file selection
        selectVideoFile();
    });

    // -------------------------------------------------------------
    // Logging Helpers
    // -------------------------------------------------------------
    function logMessage(msg, type = "info") {
        const timeStr = new Date().toLocaleTimeString();
        const line = document.createElement("div");
        line.className = `console-line ${type}`;
        line.textContent = `[${timeStr}] ${msg}`;
        consoleLogs.appendChild(line);
        consoleLogs.scrollTop = consoleLogs.scrollHeight;
    }

    btnClearLogs.addEventListener("click", () => {
        consoleLogs.innerHTML = "";
    });

    // -------------------------------------------------------------
    // Pipeline Steps Indicator
    // -------------------------------------------------------------
    const stepOrder = ["extracting", "separating", "transcribing", "translating", "dubbing", "mixing", "completed"];

    function updatePipelineSteps(currentStage) {
        let reachedCurrent = false;
        stepOrder.forEach(stage => {
            const el = document.getElementById(`pstep-${stage}`);
            if (!el) return;

            if (stage === currentStage) {
                el.className = "step-item active";
                reachedCurrent = true;
            } else if (!reachedCurrent) {
                el.className = "step-item done";
            } else {
                el.className = "step-item";
            }
        });

        if (currentStage === "completed") {
            stepOrder.forEach(stage => {
                const el = document.getElementById(`pstep-${stage}`);
                if (el) el.className = "step-item done";
            });
        }
    }

    // -------------------------------------------------------------
    // WebSocket Connection for Real-time Progress
    // -------------------------------------------------------------
    function connectWebSocket() {
        const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            logMessage("[WebSocket] បានភ្ជាប់ទំនាក់ទំនងជាមួយ Server", "info");
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                handleServerEvent(msg);
            } catch (err) {
                console.error("WS Parse error:", err);
            }
        };

        ws.onclose = () => {
            setTimeout(connectWebSocket, 3000);
        };
    }

    function handleServerEvent(data) {
        if (!data) return;

        const stage = data.stage;
        const progress = data.progress !== undefined ? data.progress : 0;
        const message = data.message || "";

        // Update progress bar
        progressBarFill.style.width = `${progress}%`;
        lblProgressPct.textContent = `${progress}%`;
        currentStageDesc.textContent = message;

        updatePipelineSteps(stage);

        if (message) {
            logMessage(message, stage === "error" ? "error" : "info");
        }

        // Live dialogue translation items
        if (stage === "translating" && data.data && data.data.khmer) {
            addDialogueCard(data.data.original, data.data.khmer);
        }

        // Completion
        if (stage === "completed" && data.data) {
            handleCompletion(data.data);
        }

        // Error
        if (stage === "error") {
            systemStatusText.textContent = "កំហុស (Error)";
            btnStartProcess.disabled = false;
            btnCancelProcess.classList.add("hidden");
        }
    }

    function addDialogueCard(orig, khmer) {
        const empty = dialogueStreamContainer.querySelector(".empty-state");
        if (empty) empty.remove();

        totalDialogueCount++;
        dialogueCountTag.textContent = `${totalDialogueCount} ឃ្លា`;

        const card = document.createElement("div");
        card.className = "dialogue-item";
        card.innerHTML = `
            <div class="dialogue-orig">${orig || "..."}</div>
            <div class="dialogue-khmer">${khmer}</div>
        `;
        dialogueStreamContainer.prepend(card);
    }

    function handleCompletion(resultData) {
        btnStartProcess.disabled = false;
        btnCancelProcess.classList.add("hidden");
        systemStatusText.textContent = "រួចរាល់ (Completed)";

        resultCard.classList.remove("hidden");
        resVideoPath.textContent = resultData.output_video;
        resSrtPath.textContent = resultData.output_srt;

        // Set video source in local preview player
        const streamUrl = `/api/video-file?path=${encodeURIComponent(resultData.output_video)}`;
        resultVideoPlayer.src = streamUrl;
        resultVideoPlayer.load();

        logMessage(`[Success] វីដេអូបានរក្សាទុកក្នុង: ${resultData.output_video}`, "success");

        // Scroll to results
        resultCard.scrollIntoView({ behavior: "smooth" });
    }

    // Open Output Folder Button
    btnOpenFolder.addEventListener("click", async () => {
        const target = resVideoPath.textContent || selectedVideoFolder;
        if (!target) return;
        try {
            await fetch("/api/open-folder", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ folder_or_file: target })
            });
        } catch (err) {
            console.error("Open folder error:", err);
        }
    });

    // -------------------------------------------------------------
    // Start Translation Action
    // -------------------------------------------------------------
    btnStartProcess.addEventListener("click", async () => {
        if (!selectedVideoPath) {
            alert("សូមជ្រើសរើសវីដេអូដើមជាមុនសិន! (Please select a video file first)");
            selectVideoFile();
            return;
        }

        const selectedVoice = document.querySelector("input[name='voiceSelect']:checked")?.value || "km-KH-PisethNeural";

        const payload = {
            video_path: selectedVideoPath,
            source_lang: selSourceLang.value,
            whisper_model: selWhisperModel.value,
            voice_id: selectedVoice,
            voice_speed: 0,
            voice_pitch: 0,
            separate_bgm: chkSeparateBgm.checked,
            bgm_volume: parseFloat(rangeBgmVol.value) / 100.0,
            dub_volume: parseFloat(rangeDubVol.value) / 100.0,
            orig_voice_volume: parseFloat(rangeOrigVol.value) / 100.0,
            burn_subtitles: chkBurnSubtitles.checked,
            save_stems: chkSaveStems.checked
        };

        btnStartProcess.disabled = true;
        btnCancelProcess.classList.remove("hidden");
        resultCard.classList.add("hidden");
        dialogueStreamContainer.innerHTML = "";
        totalDialogueCount = 0;
        dialogueCountTag.textContent = "0 ឃ្លា";
        systemStatusText.textContent = "កំពុងដំណើរការ (Processing...)";

        logMessage(`[Start] ចាប់ផ្តើមបកប្រែវីដេអូ: ${selectedFileName.textContent}...`);

        try {
            const res = await fetch("/api/start-translation", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (!res.ok) {
                alert(`កំហុស: ${data.error || "មិនអាចចាប់ផ្តើមបានទេ"}`);
                btnStartProcess.disabled = false;
                btnCancelProcess.classList.add("hidden");
            }
        } catch (err) {
            alert(`Network error: ${err}`);
            btnStartProcess.disabled = false;
            btnCancelProcess.classList.add("hidden");
        }
    });

    // Cancel Process Action
    btnCancelProcess.addEventListener("click", async () => {
        if (!confirm("តើអ្នកពិតជាចង់បញ្ឈប់ដំណើរការបកប្រែនេះមែនទេ?")) return;
        try {
            await fetch("/api/cancel", { method: "POST" });
            btnStartProcess.disabled = false;
            btnCancelProcess.classList.add("hidden");
            systemStatusText.textContent = "បានបញ្ឈប់ (Cancelled)";
            logMessage("[Cancel] ដំណើរការត្រូវបានបញ្ឈប់ដោយអ្នកប្រើប្រាស់", "error");
        } catch (err) {
            console.error("Cancel error:", err);
        }
    });

    // Initialize WebSocket
    connectWebSocket();
});
