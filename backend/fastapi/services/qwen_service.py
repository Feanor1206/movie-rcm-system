import os
import re
import glob
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MOVIES = [
    {
        "id": "the-last-orbit",
        "title": "The Last Orbit",
        "year": 2026,
        "rating": 8.7,
        "runtime": "2h 14m",
        "genres": ["Sci-Fi", "Drama"],
        "description": "A lone astronaut discovers that the signal guiding her home may be the final memory of a world already gone.",
        "poster": "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/the-last-orbit.mp4"
    },
    {
        "id": "afterlight",
        "title": "Afterlight",
        "year": 2025,
        "rating": 8.3,
        "runtime": "1h 58m",
        "genres": ["Drama", "Mystery"],
        "description": "In a city where night never ends, a photographer follows one impossible beam of sunlight.",
        "poster": "https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/afterlight.mp4"
    },
    {
        "id": "glass-horizon",
        "title": "Glass Horizon",
        "year": 2026,
        "rating": 8.1,
        "runtime": "2h 06m",
        "genres": ["Thriller", "Sci-Fi"],
        "description": "A brilliant architect is asked to design a city that no one is meant to leave.",
        "poster": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/glass-horizon.mp4"
    },
    {
        "id": "deep-blue",
        "title": "Deep Blue",
        "year": 2024,
        "rating": 7.9,
        "runtime": "1h 46m",
        "genres": ["Adventure", "Drama"],
        "description": "Two estranged sisters cross an unmapped ocean in search of their father.",
        "poster": "https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/deep-blue.mp4"
    },
    {
        "id": "quiet-places",
        "title": "Quiet Places",
        "year": 2025,
        "rating": 8.5,
        "runtime": "2h 01m",
        "genres": ["Romance", "Drama"],
        "description": "A composer returns to the town she fled and finds an old song waiting for her.",
        "poster": "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/quiet-places.mp4"
    },
    {
        "id": "nocturne",
        "title": "Nocturne",
        "year": 2024,
        "rating": 7.8,
        "runtime": "1h 52m",
        "genres": ["Crime", "Thriller"],
        "description": "A detective investigates a string of elegant crimes committed at midnight.",
        "poster": "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/nocturne.mp4"
    }
]


class QwenRecommendationService:
    def __init__(self):
        self.model_name_or_path = os.getenv("MODEL_NAME_OR_PATH", "../../ai/models/qwen-0.6b")
        self.device_config = os.getenv("DEVICE", "auto")
        self.model = None
        self.tokenizer = None
        self.llama_model = None
        self.is_loaded = False
        self.is_gguf = False
        self.actual_device = "cpu"

    def load_model(self):
        """Tải model Qwen thật từ thư mục ai/models/qwen-0.6b"""
        if self.is_loaded:
            return

        base_dir = os.path.dirname(os.path.abspath(__file__))
        search_paths = [
            self.model_name_or_path,
            os.path.join(base_dir, "../../ai/models/qwen-0.6b"),
            "../../ai/models/qwen-0.6b",
            "../ai/models/qwen-0.6b",
            "d:/movie-rcm-system/ai/models/qwen-0.6b"
        ]

        gguf_path = None
        for p in search_paths:
            if os.path.isfile(p) and p.endswith(".gguf"):
                gguf_path = p
                break
            elif os.path.isdir(p):
                found = glob.glob(os.path.join(p, "*.gguf"))
                if found:
                    gguf_path = found[0]
                    break

        if gguf_path and os.path.exists(gguf_path):
            try:
                from llama_cpp import Llama
                logger.info(f"Đang nạp model Qwen GGUF trực tiếp từ: {gguf_path}...")
                self.llama_model = Llama(
                    model_path=gguf_path,
                    n_ctx=1024,
                    n_threads=os.cpu_count() or 4,
                    verbose=False
                )
                self.is_loaded = True
                self.is_gguf = True
                self.actual_device = "llama_cpp"
                logger.info(f"Nạp model Qwen GGUF thành công từ {gguf_path}!")
                return
            except Exception as e:
                logger.error(f"Lỗi nạp qua llama-cpp: {e}")

        # Thử qua Transformers nếu không có GGUF
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer

            hf_target = self.model_name_or_path
            if not os.path.exists(hf_target) or gguf_path:
                hf_target = "Qwen/Qwen2.5-0.5B-Instruct"

            logger.info(f"Đang nạp model Qwen qua Transformers: {hf_target}...")
            device = "cuda" if (self.device_config == "auto" and torch.cuda.is_available()) else "cpu"
            self.actual_device = device
            torch_dtype = torch.float16 if device == "cuda" else torch.float32

            self.tokenizer = AutoTokenizer.from_pretrained(hf_target, trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                hf_target,
                torch_dtype=torch_dtype,
                device_map=device if device == "cuda" else None,
                trust_remote_code=True
            )
            self.is_loaded = True
            self.is_gguf = False
            logger.info(f"Nạp model Qwen Transformers thành công trên {device}!")
        except Exception as e:
            logger.error(f"Không thể nạp model Qwen: {e}")
            self.is_loaded = False

    def generate_chat_response(
        self,
        query: str,
        messages_history: Optional[List[Dict[str, Any]]] = None,
        available_movies: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Tạo câu trả lời 100% bằng Qwen LLM thực tế, KHÔNG FALLBACK"""
        if not self.is_loaded:
            self.load_model()

        catalog = available_movies if (available_movies and len(available_movies) > 0) else DEFAULT_MOVIES

        system_prompt = (
            "Bạn là CineBot - trợ lý trí tuệ nhân tạo (AI) thông minh và am hiểu điện ảnh của nền tảng Dippie Cinema. "
            "Bạn được phát triển trực tiếp trên mô hình ngôn ngữ lớn Qwen (Qwen 0.6B). "
            "Hãy xưng là 'Tôi', trả lời người dùng bằng tiếng Việt tự nhiên, chính xác, súc tích và thân thiện.\n\n"
            "Danh mục phim có sẵn trên Dippie Cinema:\n"
        )
        for m in catalog:
            system_prompt += f"- {m['title']} ({m['year']}, {m['rating']}★, {', '.join(m.get('genres', []))}): {m.get('description', '')}\n"

        system_prompt += (
            "\nQuy tắc trả lời:"
            "\n1. Nếu người dùng hỏi bạn là ai hay là model nào, hãy khẳng định bạn là CineBot chạy trên nền tảng Qwen 0.6B của Dippie Cinema."
            "\n2. Nếu người dùng hỏi hoặc yêu cầu gợi ý phim, hãy tư vấn phim phù hợp nhất trong danh mục trên và giải thích vì sao."
            "\n3. Nếu người dùng trò chuyện tự do, hãy trả lời tự nhiên theo đúng ngữ cảnh."
        )

        response_text = ""

        # 1. Chạy với Llama GGUF
        if self.is_loaded and self.is_gguf and self.llama_model:
            llama_messages = [{"role": "system", "content": system_prompt}]
            if messages_history:
                for msg in messages_history[-4:]:
                    role = msg.get("role", "user")
                    content = msg.get("content") or msg.get("text") or ""
                    if content:
                        llama_messages.append({"role": role, "content": content})
            llama_messages.append({"role": "user", "content": query})

            output = self.llama_model.create_chat_completion(
                messages=llama_messages,
                max_tokens=300,
                temperature=0.7
            )
            raw_text = output["choices"][0]["message"]["content"].strip()
            response_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()

        # 2. Chạy với Transformers
        elif self.is_loaded and self.model and self.tokenizer:
            import torch
            formatted_messages = [{"role": "system", "content": system_prompt}]
            if messages_history:
                for msg in messages_history[-4:]:
                    role = msg.get("role", "user")
                    content = msg.get("content") or msg.get("text") or ""
                    if content:
                        formatted_messages.append({"role": role, "content": content})
            formatted_messages.append({"role": "user", "content": query})

            prompt_text = self.tokenizer.apply_chat_template(
                formatted_messages,
                tokenize=False,
                add_generation_prompt=True
            )
            inputs = self.tokenizer(prompt_text, return_tensors="pt").to(self.actual_device)

            with torch.no_grad():
                output_ids = self.model.generate(
                    **inputs,
                    max_new_tokens=300,
                    temperature=0.7,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id
                )

            raw_text = self.tokenizer.decode(
                output_ids[0][inputs.input_ids.shape[1]:],
                skip_special_tokens=True
            ).strip()
            response_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()

        else:
            raise RuntimeError("Model Qwen chưa được nạp. Vui lòng kiểm tra file model trong ai/models/qwen-0.6b/!")

        # Trích xuất các phim được nhắc đến trong câu trả lời thật của model
        matched_movies = []
        for m in catalog:
            if m["title"].lower() in response_text.lower() or m["id"].lower() in response_text.lower():
                matched_movies.append(m)

        return {
            "text": response_text,
            "recommendedMovies": matched_movies,
            "followUps": [
                "Gợi ý thêm phim khoa học viễn tưởng",
                "Phim có điểm đánh giá cao nhất",
                "Tìm phim trinh thám hồi hộp"
            ]
        }


qwen_service = QwenRecommendationService()
