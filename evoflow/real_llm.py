import dashscope
from dashscope import Generation
import time

dashscope.base_http_api_url = 'https://dashscope-intl.aliyuncs.com/api/v1'
dashscope.api_key = "sk-46e10056c68741a6a2af41f11b3b8584"

MODEL_MAP = {
    "small": "qwen-turbo",
    "medium": "qwen-plus",
    "large": "qwen-plus",
}

def run_qwen_llm(model_size, prompt, temperature=0.7):
    model_name = MODEL_MAP[model_size]
    print(f"[Qwen] Starting request | model={model_name} | temperature={temperature}", flush=True)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]

    try:
        started_at = time.time()
        response = Generation.call(
            model=model_name,
            api_key=dashscope.api_key,
            messages=messages,
            temperature=temperature,
            result_format="message",
            enable_thinking=True,
            timeout=15,
        )
        elapsed = time.time() - started_at

        if response.status_code != 200:
            print(f"[Qwen] Failed after {elapsed:.2f}s | status={response.status_code} | message={response.message}", flush=True)
            return "ERROR"

        msg = response.output.choices[0].message
        reasoning = msg.get("reasoning_content", "")
        answer = msg.get("content", "")
        print(f"[Qwen] Completed successfully in {elapsed:.2f}s", flush=True)
        return reasoning + "\n" + answer if reasoning else answer

    except Exception as e:
        print(f"[Qwen] Exception during request | {e}", flush=True)
        return "ERROR"
