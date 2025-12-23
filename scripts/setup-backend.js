const { spawnSync } = require("child_process");
const path = require("path");

// Create virtual environment
const isWin = process.platform === "win32";
const backendPath = path.join(__dirname, "..", "backend");
const python = isWin ? "python.exe" : "python3";

let child = spawnSync(python, ["-m", "venv", path.join(backendPath, ".venv")], {
    cwd: backendPath,
    stdio: "inherit",
    shell: true,
});

if (child.error || child.status !== 0) {
    console.error("Failed to create virtual environment");
    process.exit(1);
}

// Install dependencies
const binPath = isWin ? "Scripts" : "bin";
const pip = isWin ? "pip.exe" : "pip";
const pipPath = path.join(backendPath, ".venv", binPath, pip);

child = spawnSync(pipPath, ["install", "-r", "requirements.txt"], {
    cwd: backendPath,
    stdio: "inherit",
    shell: true,
});

if (child.error || child.status !== 0) {
    console.error("Failed to install dependencies");
    process.exit(1);
}

process.exit(child.status);