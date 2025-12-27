const { spawn } = require("child_process");
const path = require("path");

const isWin = process.platform === "win32";
const venv = isWin ? "Scripts" : "bin";
const python = isWin ? "python.exe" : "python3";

const backendPath = path.join(__dirname, "..", "backend");
const pythonPath = path.join(backendPath, ".venv", venv, python);

// "python -u -m backend.run" from project root
const child = spawn(pythonPath, ['-u', '-m', 'backend.run'], {
    cwd: path.join(__dirname, ".."),
    stdio: "inherit",
    shell: true,
});

child.on('exit', (code) => process.exit(code));