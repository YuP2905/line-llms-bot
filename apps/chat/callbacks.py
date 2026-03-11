from typing import List, Dict, Any, Optional, cast
from transformers.tokenization_utils_base import BatchEncoding
from torch import Tensor

from qwen_vl_utils import process_vision_info

import tempfile
import base64
import torch
import os
os.environ["QWEN_VL_VIDEO_READER"] = "decord"

from core.config import settings
from services.manager import model_manager

def qwen_chat_callback(
    prompt: str,
    image_data: Optional[bytes] = None,
    video_data: Optional[bytes] = None
) -> str:
    global settings

    if model_manager.qwen_model is None or model_manager.qwen_processor is None:
        raise RuntimeError(
            "Qwen model or processor not loaded"
        )

    processor = model_manager.qwen_processor
    model = model_manager.qwen_model

    content: List[Dict[str, str|int]] = []
    temp_video_path: Optional[str] = None

    try:
        if image_data is not None:
            img = base64.b64encode(image_data).decode("utf-8")
            img = f"data:image/png;base64,{img}"
            content.append({
                "type": "image",
                "image": img,
                "min_pixels": settings.IMAGE_MIN_PIXELS,
                "max_pixels": settings.IMAGE_MAX_PIXELS
            })
        elif video_data is not None:
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            temp_file.write(video_data)
            temp_file.close()
            temp_video_path = temp_file.name

            content.append({
                "type": "video",
                "video": temp_video_path,
                "max_pixels": settings.VIDEO_MAX_PIXELS,
                "fps": settings.VIDEO_FPS,
            })

        content.append({
            "type": "text",
            "text": prompt
        })

        messages:List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": settings.SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": content
            }
        ]

        text = processor.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        image_inputs, or_video_inputs, video_kwargs = process_vision_info(
            messages,
            return_video_kwargs=True,
            return_video_metadata=True
        )

        video_inputs: Optional[List[Tensor]] = None
        video_metadata: Optional[List[Dict[str, Any]]] = None

        if or_video_inputs is not None:
            video_inputs = [v[0] for v in or_video_inputs]
            video_metadata = [v[1] for v in or_video_inputs]

        inputs = cast(BatchEncoding, processor(
            text=[text],
            images=image_inputs,
            videos=video_inputs,
            video_metadata=video_metadata,
            padding=True,
            return_tensors="pt",
            **video_kwargs
        )).to(model_manager.device)

        with torch.no_grad():
            generated_ids = model.generate(
                **inputs,
                max_new_tokens=settings.MAX_NEW_TOKENS,
                do_sample=settings.DO_SAMPLE,
                temperature=settings.TEMPERATURE,
                top_p=settings.TOP_P,
            )

        input_ids = cast(Tensor, inputs["input_ids"])
        generated_ids_trimmed: List[Tensor] = [
                out_ids[len(in_ids):] for in_ids, out_ids in zip(input_ids, generated_ids)
            ]
        output_text: List[str] = processor.batch_decode(
                generated_ids_trimmed,
                skip_special_tokens=True,
                clean_up_tokenization_spaces=False
            )

        return output_text[0].strip()

    finally:
        if temp_video_path is not None and os.path.exists(temp_video_path):
            os.remove(temp_video_path)