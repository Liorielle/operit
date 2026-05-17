import httpx
import json
import os

async def stream_forward(parsed_data, response_container: list):
    base_url = os.getenv("LLM_BASE_URL", "").rstrip("/")
    api_key = os.getenv("LLM_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    full_response = []

    if "stream_options" not in parsed_data["body"]:
        parsed_data["body"]["stream_options"] = {"include_usage": True}

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            json=parsed_data["body"],
            headers=headers,
            timeout=60
        ) as response:
            async for chunk in response.aiter_text():
                if not chunk:
                    continue

                yield chunk

                for line in chunk.split('\n'):
                    if line.startswith('data: ') and line != 'data: [DONE]':
                        try:
                            data = json.loads(line[6:])

                            if 'choices' in data and len(data['choices']) > 0:
                                content = data['choices'][0]['delta'].get('content', '')
                                full_response.append(content)

                            if 'usage' in data and data['usage'] is not None:
                                usage = data['usage']
                                total_prompt = usage.get('prompt_tokens', 0)
                                cached_prompt = 0
                                if 'prompt_tokens_details' in usage:
                                    cached_prompt = usage['prompt_tokens_details'].get('cached_tokens', 0)
                                completion = usage.get('completion_tokens', 0)
                                hit_rate = f"{cached_prompt/total_prompt*100:.1f}%" if total_prompt > 0 else "N/A"
                                print(f"│ 💰 发送:{total_prompt} 缓存命中:{cached_prompt} 命中率:{hit_rate} 回复:{completion}")
                        except:
                            pass

    response_container.append(''.join(full_response))
