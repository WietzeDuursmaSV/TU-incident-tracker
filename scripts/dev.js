const { spawnSync } = require("node:child_process");
const fs = require("node:fs");

const isWindows = process.platform === "win32";
const port = process.env.PORT || "5001";

const venvPython = isWindows ? ".venv\\Scripts\\python.exe" : ".venv/bin/python";

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    stdio: "inherit",
    shell: false,
    ...options,
  });

  if (result.error) {
    throw result.error;
  }

  if (typeof result.status === "number" && result.status !== 0) {
    process.exit(result.status);
  }
}

function runCapture(command, args, options = {}) {
  const result = spawnSync(command, args, {
    encoding: "utf8",
    stdio: ["ignore", "pipe", "pipe"],
    shell: false,
    ...options,
  });

  if (result.error) {
    return {
      status: 1,
      stdout: "",
      stderr: String(result.error.message || result.error),
      error: result.error,
    };
  }

  return result;
}

function killProcessOnPort(targetPort) {
  if (isWindows) {
    const psScript = [
      `$connections = Get-NetTCPConnection -LocalPort ${targetPort} -State Listen -ErrorAction SilentlyContinue`,
      "if ($connections) {",
      "  $connections | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object {",
      "    Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue",
      "  }",
      "}",
    ].join("; ");

    runCapture("powershell", ["-NoProfile", "-Command", psScript]);
    return;
  }

  const lsof = runCapture("lsof", ["-ti", `tcp:${targetPort}`]);
  if (lsof.status !== 0 || !lsof.stdout.trim()) {
    return;
  }

  const pids = lsof.stdout
    .split(/\r?\n/)
    .map((pid) => pid.trim())
    .filter(Boolean);

  for (const pid of pids) {
    run("kill", [pid]);
  }
}

function ensureVirtualEnv() {
  if (fs.existsSync(venvPython)) {
    return;
  }

  const pythonCandidates = isWindows ? ["py", "python", "python3"] : ["python3", "python"];
  let selectedPython = "";

  for (const candidate of pythonCandidates) {
    const check = runCapture(candidate, ["--version"]);
    if (check.status === 0) {
      selectedPython = candidate;
      break;
    }
  }

  if (!selectedPython) {
    console.error("Geen Python-installatie gevonden om de virtuele omgeving aan te maken.");
    process.exit(1);
  }

  run(selectedPython, ["-m", "venv", ".venv"]);
  run(venvPython, ["-m", "pip", "install", "-r", "requirements.txt"]);
}

function startApp(targetPort) {
  run(venvPython, ["app.py"], {
    env: {
      ...process.env,
      PORT: String(targetPort),
    },
  });
}

killProcessOnPort(port);
ensureVirtualEnv();
startApp(port);