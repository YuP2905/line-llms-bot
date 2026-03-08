from typing import Optional, Callable, TypeVar, cast, TYPE_CHECKING
if TYPE_CHECKING:
    from torch._C import _CudaDeviceProperties # type: ignore[import]

from typing_extensions import ParamSpec
from asyncio import Lock

from transformers import (
    BitsAndBytesConfig,
    Qwen3VLForConditionalGeneration,
    Qwen3VLProcessor,
)

from diffusers import StableDiffusionPipeline
import functools
import asyncio
import torch
import gc

from core.config import settings
from services.types import MODEL_MODE

P = ParamSpec('P')
T = TypeVar('T')

class ModelManager:
    __slots__ = (
        "current_model",
        "device",
        "compute_dtype",
        "qwen_model",
        "qwen_processor",
        "sd_pipeline",
        "lock"
    )

    def __init__(
        self
    ) -> None:
        self.current_model: MODEL_MODE = ''

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        compute_dtype = torch.float16
        if torch.cuda.is_available() and torch.cuda.get_device_capability()[0] >= 8:
            compute_dtype = torch.bfloat16
        self.compute_dtype = compute_dtype

        self.qwen_model: Optional[Qwen3VLForConditionalGeneration] = None
        self.qwen_processor: Optional[Qwen3VLProcessor] = None

        self.sd_pipeline: Optional[StableDiffusionPipeline] = None
        self.lock: Lock = asyncio.Lock()

    def clean(
        self
    ):
        self.qwen_model = None
        self.qwen_processor = None
        self.sd_pipeline = None

        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        self.current_model = ''

    async def safe_inference(
        self,
        task_type: MODEL_MODE,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        async with self.lock:
            if task_type == "qwen_multi":
                self.load_qwen_model()
            elif task_type == "image_gen":
                self.load_sd_model()
            else:
                raise ValueError(
                    f"Unsupported task type: {task_type}"
                )
            loop = asyncio.get_event_loop()
            task = functools.partial(func, *args, **kwargs)
            res = cast(T, await loop.run_in_executor(
                None,
                task
            ))
            return res

    def _get_quant_config(
            self
        ) -> BitsAndBytesConfig:

            # 1660 Ti: float16; 4060: bfloat16
            return BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=self.compute_dtype ,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True
            )

    def load_qwen_model(
        self
    ):
        global settings
        if self.current_model == "qwen_multi":
            return

        self.clean()

        model_id = settings.MIN_QWEN_MODEL_ID
        if self.device == "cuda":
            total_gpu_mem = cast(
                "_CudaDeviceProperties",
                torch.cuda.get_device_properties(0)
            ).total_memory / (1024 ** 3)  # Convert to GB

            if total_gpu_mem >= settings.MID_GPU_MEM_THRESHOLD:
                model_id = settings.MID_QWEN_MODEL_ID
            elif total_gpu_mem >= settings.MAX_GPU_MEM_THRESHOLD:
                model_id = settings.MAX_QWEN_MODEL_ID
            elif total_gpu_mem >= settings.SUPPER_GPU_MEM_THRESHOLD:
                model_id = settings.SUPPER_QWEN_MODEL_ID

        if not model_id:
            raise ValueError(
                "QWEN_MODEL_ID is not set in environment variables."
            )

        quant_config = self._get_quant_config()

        self.qwen_processor = Qwen3VLProcessor.from_pretrained(model_id)
        self.qwen_model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_id,
            quantization_config=quant_config,
            device_map="auto",
            dtype=self.compute_dtype
        )

        self.current_model = "qwen_multi"

    def load_sd_model(
        self
    ) -> None:
        if self.current_model == "image_gen":
            return

        self.clean()

        # model_id: Optional[str] = settings.DIFFUSION_MODEL_ID

        # if not model_id:
        #     raise ValueError(
        #         "SD_MODEL_ID is not set in environment variables."
        #     )

        # self.sd_pipeline = StableDiffusionPipeline.from_pretrained(
        #     model_id,
        #     torch_dtype=torch.float16
        # ).to(self.device)

        # # Enable attention slicing for better performance on limited VRAM
        # if self.sd_pipeline:
        #     self.sd_pipeline.enable_attention_slicing()

        # self.current_model = "image_gen"

        raise NotImplementedError(
            "Stable Diffusion model loading is not implemented yet."
        )

model_manager = ModelManager()