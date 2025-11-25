<br>

<p align="center">
    <img alt="GalaxyAI" src="./docs/assets/GalaxyAI-logo.png" width="300px"/>
</p>
<br>

<br>


#### 介绍
银河智能操作系统（GalaxyAIOS）围绕AI大模型技术构建，专为大模型应用全生命周期（部署、推理、迭代、运维）设计的专用操作系统，其核心价值是 “为大模型落地提供端到端的标准化支撑环境”，解决 “模型与硬件、场景与工具、安全与效率” 的协同难题，原生集成依赖管理、资源调度、模型服务、智能体和知识库等工具，针对主流AI框架（如PyTorch）和大模型推理引擎进行内核级、库级的深度优化，大幅降低部署和运维复杂度，实现“智能平权、解放创造力”的AI共生体，开启人机共生的新纪元：
1.	专用性：聚焦大模型推理场景，如针对模型服务的分布式算力调度、针对推理的低延迟优化；
2.	模型应用全生命周期覆盖：从模型管理到模型部署上线、升级迭代、安全运维，提供一站式支撑，避免企业拼接多工具的 “碎片化” 困境；
3.	生态兼容性：既兼容开源生态（如 Hugging Face 模型库、GitHub 社区工具），也支持商业生态（如厂商闭源模型、企业智能体应用商店），平衡开放与安全。

#### 软件架构
核心构成：三层架构支撑全流程能力
1.	内核层：基于 Linux 内核扩展 AI 专用模块，支持异构计算（支持 GPU/TPU/NPU ）、模型运行工具链（GPU驱动/CUDA/pytorch）、大模型内存和存储管理等
2.	平台层：集成推理引擎/微调框架，提供经过认证的模型库，包含性能优化（TensorRT/ONNX 加速）、RAG/向量数据库/langchain/MCP等组件和SDK，支持容器部署和云边部署、模型可观测等能力
3.	应用层：提供主流的智能体/工作流工具和应用，AI应用市场中包括ComfyUI/dify/知识库等常见的主流应用。


### 核心特性

- **分布式算力整合**：通过去中心化网络协议整合闲置算力资源形成分布式AI算力池，用户贡献的GPU资源可参与算力交易市场的流通，实现“算力即资产”的生态闭环。
- **全栈开源的智能底座**：提供统一的操作系统内核和开发框架、编排调度系统、开发环境，支持k8s、Ray、Docker，助力AI应用快速集成开发。
- **性能优化的推理引擎**：支持经过优化的多推理引擎，如llama.cpp、vLLM、Trition、BentoML等，支持Transformer、Diffusion、MOE、Lora等主流的算法架构。
- **包含丰富的开源模型**：模型市场预集成开源模型（如Llama3、Qwen、DeepSeek、SD、FLUX、Whisper等），支持广泛的模型，从大语言模型、文生图扩散模型、STT 与 TTS 语音模型、多模态模型等，支持百亿至万亿级参数模型。
- **完善的开源工具链**：集成Langchain、dify、RagFlow、Milvus等工具链和中间件，可帮助开发者极大提高AI应用开发效率。  
- **多智能体协同引擎**：通过MCP协议实现自然语言处理（NLP）、计算机视觉（CV）、语音交互等能力的协同调用。例如，文本生成模型可联动文生图模型完成系列漫画的制作。
- **广泛的兼容性**：支持Apple Mac、Windows 和 Linux不同的OS和NVIDIA、AMD GPU，轻松添加异构 GPU 资源。
- **OpenAI 兼容 API**：提供兼容 OpenAI 标准的 API 服务。
- **用户和 API 密钥管理**：简化用户和 API 密钥的管理流程。

### 主要特点

- **去中心化**：通过去中心化协议连接全球用户的计算设备，构建一个无需依赖中心服务器的世界超级AI计算机
- **效益优势**：允许用户贡献自己的闲置计算资源换取奖励，同时可降低使用AI模型的成本
- **AI神兽**：构建普惠的超级AI智能体，实现智能平权，共享AI时代红利
- **激励机制**：基于积分的奖励机制，开发者 运营者 用户可以和项目共同成长（POC机制），激励用户积极参与项目贡献和建设
- **开源开放**：鼓励社区成员参与项目的开发、维护和发展，形成活跃且持续进化的开源生态系统，开放理念共创共建价值网络


## 安装

### Windows

官网下载wsl镜像：

[GalaxyAI](https://www.aiverse.vip/GalaxyAI/GalaxyAIOS_V0.1_win.tgz)

### 其他安装方式

有关手动安装、Docker 安装或详细配置选项，请参考帮助手册。

## 新手入门

1. 加入算力网络
    ```bash
    GalaxyAI join 
    ```

2. 在浏览器中打开 `http://127.0.0.1:12888`，使用"admin/admin"登录


```
使用方法：
进入docker目录：cd GalaxyAIOS/docker
启动系统：./start.sh
停止系统：./stop.sh
系统启动后：
Web界面：http://localhost:12888
API接口：http://localhost:9999
默认用户名：admin
默认密码：admin
```


## 平台支持

- [x] Linux
- [x] Windows

## 加速框架支持

- [x] NVIDIA CUDA ([Compute Capability](https://developer.nvidia.com/cuda-gpus) 6.0 以上)

我们计划在未来的版本中支持以下加速框架：
- [x] AMD ROCm
- [ ] 海光 DCU
- [ ] 昇腾 CANN
- [ ] Intel oneAPI
- [ ] Apple Metal (M 系列芯片)

## 模型支持

支持从以下来源部署模型：

1. [Hugging Face](https://huggingface.co/)

2. [ModelScope](https://modelscope.cn/)

3. 本地文件路径

### 示例模型

| **类别**               | **模型**                                                                                                                                                                                                                                                                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **大语言模型（LLM）**  | [Qwen](https://huggingface.co/models?search=Qwen/Qwen), [LLaMA](https://huggingface.co/meta-llama), [Mistral](https://huggingface.co/mistralai), [Deepseek](https://huggingface.co/models?search=deepseek-ai/deepseek), [Phi](https://huggingface.co/models?search=microsoft/phi), [Yi](https://huggingface.co/models?search=01-ai/Yi)           |
| **多模态模型（VLM）**  | [Llama3.2-Vision](https://huggingface.co/models?pipeline_tag=image-text-to-text&search=llama3.2), [Pixtral](https://huggingface.co/models?search=pixtral) , [Qwen2-VL](https://huggingface.co/models?search=Qwen/Qwen2-VL), [LLaVA](https://huggingface.co/models?search=llava), [InternVL2.5](https://huggingface.co/models?search=internvl2_5) |
| **Diffusion 扩散模型** | [Stable Diffusion](https://huggingface.co/models?search=stable-diffusion), [FLUX](https://huggingface.co/models?search=flux) 
| **语音模型**           | [Whisper](https://huggingface.co/models?search=Systran/faster) (speech-to-text), [CosyVoice](https://huggingface.co/models?search=FunAudioLLM/CosyVoice) (text-to-speech)                                                                                                                                                                        |


## OpenAI 兼容 API

 `/v1-openai` 路径提供以下 OpenAI 兼容 API：

- [x] [List Models](https://platform.openai.com/docs/api-reference/models/list)
- [x] [Create Completion](https://platform.openai.com/docs/api-reference/completions/create)
- [x] [Create Chat Completion](https://platform.openai.com/docs/api-reference/chat/create)
- [x] [Create Embeddings](https://platform.openai.com/docs/api-reference/embeddings/create)
- [x] [Create Image](https://platform.openai.com/docs/api-reference/images/create)
- [x] [Create Image Edit](https://platform.openai.com/docs/api-reference/images/createEdit)
- [x] [Create Speech](https://platform.openai.com/docs/api-reference/audio/createSpeech)
- [x] [Create Transcription](https://platform.openai.com/docs/api-reference/audio/createTranscription)

例如，你可以使用官方的 [OpenAI Python API 库](https://github.com/openai/openai-python)来调用 API：

```python
from openai import OpenAI
client = OpenAI(base_url="http://myserver/v1-openai", api_key="myapikey")

completion = client.chat.completions.create(
  model="llama3.2",
  messages=[
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello!"}
  ]
)

print(completion.choices[0].message)
```

用户可以在 UI 中生成自己的 API 密钥。

## 文档

完整文档请参见官方文档。


## 参与贡献

欢迎参与贡献代码：https://github.com/GalaxyAI888/GalaxyAIOS.git

## 加入社区

欢迎加入社区群。

