from dataclasses import dataclass
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from mini_researcher.models import Usage


ModelT = TypeVar("ModelT", bound=BaseModel)


class LLMError(RuntimeError):
    """A provider-independent LLM failure."""


@dataclass(frozen=True)
class LLMResult(Generic[ModelT]):
    value: ModelT
    usage: Usage


class LLMClient(Protocol):
    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_type: type[ModelT],
    ) -> LLMResult[ModelT]: ...


class DeepSeekLLM:
    def __init__(
        self,
        client: Any | None = None,
        *,
        api_key: str | None = None,
        base_url: str = "https://api.deepseek.com",
        model: str = "deepseek-v4-flash",
    ) -> None:
        if client is None:
            if not api_key:
                raise ValueError("api_key is required when client is not provided")
            from openai import OpenAI

            client = OpenAI(api_key=api_key, base_url=base_url)
        self.client = client
        self.model = model

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        output_type: type[ModelT],
    ) -> LLMResult[ModelT]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        input_tokens = 0
        output_tokens = 0
        try:
            for attempt in range(2):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    response_format={"type": "json_object"},
                    extra_body={"thinking": {"type": "disabled"}},
                )
                provider_usage = response.usage
                input_tokens += getattr(provider_usage, "prompt_tokens", 0) or 0
                output_tokens += getattr(provider_usage, "completion_tokens", 0) or 0
                content = response.choices[0].message.content
                if not content:
                    raise ValueError("LLM returned empty content")
                try:
                    value = output_type.model_validate_json(content)
                except ValidationError:
                    if attempt == 0:
                        continue
                    raise
                return LLMResult(
                    value=value,
                    usage=Usage(
                        llm_requests=attempt + 1,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    ),
                )
            raise RuntimeError("unreachable")
        except (ValueError, ValidationError):
            raise
        except Exception as error:
            raise LLMError("DeepSeek request failed") from error
