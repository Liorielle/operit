import httpx
import json
import os

async def stream_forward(parsed_data, response_container: list):
    """
    流式转发函数

    参数：
    - parsed_data: 解析后的请求数据（来自 mod_parse/parser.py）
    - response_container: 列表容器，用于存储完整回复
    """

    base_url = os.getenv("LLM_BASE_URL")
    api_key = os.getenv("LLM_API_KEY")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    full_response = []  # 本地拼凑完整回复

    # 👇 1. 强行要求老教授开小票：加入 stream_options 选项
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

                # ========== 实时转发给客户端 ==========
                yield chunk

                # ========== 后台拼凑完整回复 与 截获账单 ==========
                for line in chunk.split('\n'):
                    if line.startswith('data: ') and line != 'data: [DONE]':
                        try:
                            data = json.loads(line[6:])
                            
                            # 正常提取 AI 说的字，拼凑记录
                            if 'choices' in data and len(data['choices']) > 0:
                                content = data['choices'][0]['delta'].get('content', '')
                                full_response.append(content)
                            
                            # 👇 2. 账单打印机：寻找包裹底部的 usage 小票！
                            if 'usage' in data and data['usage'] is not None:
                                usage = data['usage']
                                total_prompt = usage.get('prompt_tokens', 0)
                                
                                # 读取缓存省下的字数（完美兼容各大模型的缓存字段）
                                cached_prompt = 0
                                if 'prompt_tokens_details' in usage:
                                    cached_prompt = usage['prompt_tokens_details'].get('cached_tokens', 0)
                                    
                                print(f"\n💰 【账单打印机】老教授开票啦！")
                                print(f"   👉 发送总字数: {total_prompt}")
                                print(f"   🎉 命中缓存(免单): {cached_prompt}")
                                if cached_prompt > 0:
                                    print(f"   ✨ 太棒了！成功白嫖了 {cached_prompt} 个 Token 的阅读费！")
                                else:
                                    print(f"   🐌 没命中缓存。老教授全篇重读了（注意：如果是刚开新窗口第一句话，没命中是正常的，下句话就会命中了！）\n")
                        except Exception as e:
                            pass

    # ========== 流式结束：存入容器 ==========
    response_container.append(''.join(full_response))
