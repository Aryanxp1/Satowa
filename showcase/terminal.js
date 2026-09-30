/**
 * Aceternity UI Terminal Engine for Setowa Showcase
 * Exactly matches https://ui.aceternity.com/components/terminal
 */
(() => {
  const PROMPT_LABEL = "PS C:\\Users\\lex\\Setowa> ";

  const commands = [
    "git clone https://github.com/Aryanxp1/Satowa.git Satowa && cd Satowa",
    ".\\run_local.bat",
    "python -m app.cli run-dag --dag mombasa_restoration"
  ];

  const outputs = {
    0: [
      "Cloning into 'Setowa'...",
      "✓ Repository cloned successfully (Windows 64-bit)",
      "✓ Preflight checks passed (Python 3.11, Cloudinary SDK, NetworkX)"
    ],
    1: [
      "✓ Verified Python 3.11 virtualenv (backend\\venv)",
      "✓ Installed dependencies (FastAPI, Cloudinary SDK, NetworkX)",
      "✓ Database & seeded restoration models loaded",
      "✓ Setowa server live on http://127.0.0.1:8000 (PID: 8314)"
    ],
    2: [
      "✓ Visual DAG loaded: mombasa_restoration (5 nodes, 0 cycles)",
      "✓ [Skill: video_frames] 12 keyframes extracted in 0.38s",
      "✓ [Skill: debris_diff] -68.4% surface marine plastic verified",
      "✓ [Human Gate] Signed & approved by Aryan (Field Lead)",
      "✓ Cryptographic audit spine sealed: sha256:8f2a...49e0"
    ]
  };

  const TYPING_SPEED = 38;
  const DELAY_AFTER_TYPING = 320;
  const DELAY_BETWEEN_OUTPUTS = 140;
  const DELAY_BETWEEN_COMMANDS = 1100;
  const RESTART_PAUSE = 6000;

  function initAceternityTerminal() {
    const termBody = document.getElementById("aceternity-terminal-body");
    if (!termBody) return;

    let timeoutId = null;

    function runAnimation() {
      if (timeoutId) clearTimeout(timeoutId);
      termBody.innerHTML = "";

      let cmdIndex = 0;

      function runNextCommand() {
        if (cmdIndex >= commands.length) {
          // Finished all commands: display idle blinking prompt, then restart
          const idleLine = document.createElement("div");
          idleLine.className = "term-line term-line-prompt";
          idleLine.innerHTML = `<span class="term-ps-prompt">${escapeHtml(PROMPT_LABEL)}</span><span class="term-cursor-block"></span>`;
          termBody.appendChild(idleLine);
          termBody.scrollTop = termBody.scrollHeight;

          timeoutId = setTimeout(() => {
            runAnimation();
          }, RESTART_PAUSE);
          return;
        }

        const currentCmd = commands[cmdIndex];
        const currentOutputs = outputs[cmdIndex] || [];

        // Prompt line for this command
        const promptLine = document.createElement("div");
        promptLine.className = "term-line term-line-prompt";
        promptLine.innerHTML = `<span class="term-ps-prompt">${escapeHtml(PROMPT_LABEL)}</span><span class="term-command"></span><span class="term-cursor-block"></span>`;
        termBody.appendChild(promptLine);

        const cmdSpan = promptLine.querySelector(".term-command");
        const cursor = promptLine.querySelector(".term-cursor-block");

        let charIdx = 0;

        function typeNextChar() {
          if (charIdx < currentCmd.length) {
            cmdSpan.textContent += currentCmd[charIdx];
            charIdx++;
            termBody.scrollTop = termBody.scrollHeight;
            timeoutId = setTimeout(typeNextChar, TYPING_SPEED + Math.random() * 15);
          } else {
            // Command typing complete; remove active cursor from prompt
            cursor.remove();

            timeoutId = setTimeout(() => {
              // Print output lines
              printOutputs(currentOutputs, 0, () => {
                cmdIndex++;
                timeoutId = setTimeout(runNextCommand, DELAY_BETWEEN_COMMANDS);
              });
            }, DELAY_AFTER_TYPING);
          }
        }

        timeoutId = setTimeout(typeNextChar, 200);
      }

      function printOutputs(lines, lineIdx, onComplete) {
        if (lineIdx >= lines.length) {
          if (onComplete) onComplete();
          return;
        }

        const text = lines[lineIdx];
        const outDiv = document.createElement("div");
        outDiv.className = "term-line term-output";

        if (text.startsWith("✓") || text.startsWith("✔")) {
          outDiv.classList.add("term-output-success");
          outDiv.innerHTML = `<span class="term-output-check">✓</span> ${escapeHtml(text.replace(/^[✓✔]\s*/, ""))}`;
        } else if (text.includes("http://")) {
          const parts = text.split("http://127.0.0.1:8000");
          outDiv.innerHTML = `${escapeHtml(parts[0])}<span class="term-output-highlight">http://127.0.0.1:8000</span>${escapeHtml(parts[1] || "")}`;
        } else {
          outDiv.textContent = text;
        }

        termBody.appendChild(outDiv);
        termBody.scrollTop = termBody.scrollHeight;

        timeoutId = setTimeout(() => {
          printOutputs(lines, lineIdx + 1, onComplete);
        }, DELAY_BETWEEN_OUTPUTS);
      }

      runNextCommand();
    }

    function escapeHtml(str) {
      return str.replace(/[&<>"']/g, (m) => {
        switch (m) {
          case '&': return '&amp;';
          case '<': return '&lt;';
          case '>': return '&gt;';
          case '"': return '&quot;';
          case "'": return '&#39;';
          default: return m;
        }
      });
    }

    runAnimation();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initAceternityTerminal);
  } else {
    initAceternityTerminal();
  }
})();
