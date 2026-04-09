import dashscope
from dashscope import Generation
dashscope.api_key = "sk-46e10056c68741a6a2af41f11b3b8584" 
response = Generation.call(model=Generation.Models.qwen_turbo, prompt="测试")
print(response)