from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
import os
import shutil
import tempfile
from pathlib import Path
import logging
import time

from faster_whisper import WhisperModel

# Router definition
router = APIRouter(
    prefix="/speech",
    tags=["speech"],
    responses={404: {"description": "Not found"}},
)

logger = logging.getLogger("uvicorn.error")

# Model configuration
# モデルサイズ: tiny, base, small, medium, large-v2, large-v3
# 多言語対応モデル推奨 (英語専用は .en がつく)
MODEL_SIZE = "small" 
DEVICE = "cpu" # GPUがある場合は "cuda"
COMPUTE_TYPE = "int8" # CPUなら "int8", GPUなら "float16" or "int8_float16"

print(f"[STT] Loading Faster-Whisper model ({MODEL_SIZE})...")
try:
    # モデルのロード（初回はダウンロードが発生）
    model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print(f"[STT] Model loaded successfully.")
except Exception as e:
    logger.error(f"[STT] Failed to load model: {e}")
    model = None

@router.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(...),
):
    """
    Receives an audio file, saves it temporarily, and transcribes it using Faster-Whisper.
    """
    if model is None:
        raise HTTPException(status_code=500, detail="STT Model is not loaded")

    # Create a temporary file to save the uploaded audio
    suffix = Path(file.filename).suffix or ".webm"
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        try:
            # 1. Save uploaded file to disk
            content = await file.read()
            if len(content) == 0:
                raise HTTPException(status_code=400, detail="Empty file uploaded")
                
            tmp.write(content)
            tmp_path = tmp.name
            
            logger.info(f"[STT] Received audio: {file.filename} -> {tmp_path}")

            # 2. Transcribe
            start_time = time.time()
            
            # segments, info = model.transcribe(audio, beam_size=5)
            # language="ja" を指定すると精度が上がることがある
            segments, info = model.transcribe(tmp_path, beam_size=5, language="ja")
            
            transcribed_text = ""
            for segment in segments:
                transcribed_text += segment.text
            
            duration = time.time() - start_time
            
            logger.info(f"[STT] Transcription complete ({duration:.2f}s): {transcribed_text}")
            logger.info(f"[STT] Detected language: {info.language} with probability {info.language_probability}")

            return JSONResponse(content={
                "status": "ok",
                "text": transcribed_text.strip(),
                "duration": duration,
                "language": info.language
            })

        except Exception as e:
            logger.error(f"[STT] Error during transcription: {e}", exc_info=True)
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": str(e)}
            )
        finally:
            # Clean up temp file
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception as e:
                logger.warning(f"[STT] Failed to remove temp file: {e}")
