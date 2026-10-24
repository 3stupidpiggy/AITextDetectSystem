# AI 文本检测系统

面向人机混合文本的细粒度 AI 生成内容检测系统。系统以句子为基本单元判断文本的生成来源，并进一步在句子内部定位人机内容的切换位置，通过词汇级高亮、句子级置信度与切换点标注，直观呈现文本中疑似 AI 生成的片段。

本项目为第一届湖南省研究生网络安全创新大赛参赛作品，作品名称为「基于滑动窗口的多粒度人机混合文本检测系统」。

## 项目背景

随着生成式人工智能技术的普及，AI 生成文本在新闻、学术写作和内容创作中的占比越来越高，人工撰写与 AI 生成内容相互交织的情况也越来越常见。传统的整篇检测方式只能给出一个整体判断，难以回答「哪一段、哪一句、甚至哪几个词是 AI 写的」。

本系统围绕这一问题，采用句子级与单词级相结合的双粒度检测方案：句子级负责定位疑似 AI 生成的语句，单词级进一步细化到词元，标出人机内容的切换边界。检测结果以网页形式呈现，并配套用户认证、历史记录和结果导出功能，形成一套可直接使用的文本检测工具。

## 项目亮点

- **双粒度检测**：句子级定位疑似 AI 语句，单词级细化到词元并标出切换边界，避免整篇判断的粗粒度问题；
- **上下文噪声抑制**：通过多窗口上下文建模与置信度加权融合，降低不同来源上下文对目标句子判断的干扰；
- **自适应滑动窗口**：根据文本长度动态调整窗口与步长，兼顾短文本的上下文覆盖与长文本的计算开销；
- **完整工程实现**：检测算法、文件解析、结果可视化、用户认证与历史管理集成于同一系统，支持本地化部署。

## 功能特性

| 模块 | 能力 |
| --- | --- |
| 用户认证 | 注册、登录，JWT 令牌校验，PBKDF2-HMAC-SHA256 加盐存储口令 |
| 文本检测 | 句子级分类与单词级标注，返回人机切换点 |
| 文件导入 | 支持 `.txt`（UTF-8 / GBK）、`.docx`、`.doc` |
| 内置样例 | 5 条样例，覆盖纯人类、纯 AI、连续混写、句内插入与中英混排 |
| 结果可视化 | 词汇级红绿高亮、切换点虚线标记、句子卡片与置信度 |
| 历史记录 | 按今日 / 7 天内 / 更久分组，支持详情查看、单条导出与清空 |
| 结果导出 | JSON（结构化）与 TXT（可读文本）两种格式 |
| 性能测试 | 提供 JMeter 压测脚本与测试报告 |

## 检测示例

| 样例 | 文本类型 | 检测结果 |
| --- | --- | --- |
| 样例3 | 两段人类写作 + 一段 AI 续写 | `H153 A170`，第 5 句第 154 个词切换为 AI |
| 样例4 | 人类写作句子中插入 AI 从句 | `H83 A39 H116`，仅中间 39 个字符标注为 AI |
| 样例5 | 中英混排长文本 | `H527`，全篇判定为人类 |

## 系统架构

系统采用前后端分离的 B/S 架构。前端负责页面渲染与交互，通过 JSON 接口与后端通信；后端基于 FastAPI，业务层统一调度句子级与单词级两类检测器；数据层使用 SQLite 保存用户与检测记录。

```
浏览器（HTML / CSS / JavaScript）
        │  JSON / JWT
        ▼
FastAPI 路由 ──► 检测服务 ──► 句子级检测器
        │                    └► 词汇级检测器
        ▼
SQLite（用户、历史记录）
```

一次完整检测的处理流程如下：

1. 用户输入文本、上传文件或加载内置样例；
2. 后端完成文本解析、分句、分词与字符定位；
3. 句子级检测器通过滑动窗口构建局部上下文，融合语义特征与增量困惑度特征，经置信度加权得到句子标签；
4. 单词级检测器基于 DeBERTa + CRF 完成序列标注，结合自适应窗口与全局累计得分定位切换边界；
5. 业务层整合两类结果，返回句子标签、词元标签、置信度与字符位置；
6. 前端渲染高亮与卡片，并将本次检测写入历史记录。

## 技术栈

| 层次 | 技术选型 |
| --- | --- |
| 前端 | HTML5、CSS3、原生 JavaScript |
| Web 框架 | FastAPI、Uvicorn、Jinja2 |
| 数据校验 | Pydantic |
| 数据存储 | SQLite |
| 文档解析 | python-docx、pywin32（`.doc`） |
| 模型推理（可选） | PyTorch、Transformers、TorchCRF、sentencepiece |
| 性能测试 | Apache JMeter |

## 目录结构

```
web/
├── aigc_web/
│   ├── app/
│   │   ├── main.py               # 页面路由与 API 接口
│   │   ├── service.py            # 检测流程编排
│   │   ├── auth.py               # 注册、登录、令牌校验
│   │   ├── config.py             # 路径与环境变量
│   │   ├── file_parser.py        # TXT / DOCX / DOC 解析
│   │   ├── detectors/            # 句子级与单词级检测器
│   │   ├── templates/            # Jinja2 页面模板
│   │   ├── static/               # CSS、JavaScript
│   │   └── data/samples.json     # 内置样例
│   └── perf/                     # JMeter 脚本与压测报告
├── scripts/                      # 可独立运行的模型推理脚本
├── run.py                        # 启动入口
├── requirements.txt              # 依赖清单
├── README.md
└── DEPLOYMENT.md
```

## 快速开始

### 环境要求

- Python 3.9 ~ 3.12（本机在 3.9.23 上验证）
- Windows 10 / 11；Linux、macOS 可运行，但 `.doc` 解析依赖本机 Microsoft Word
- 可选：NVIDIA GPU + CUDA（启用模型通道时）

### 安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`requirements.txt` 中模型推理依赖默认注释，不安装也可正常启动，系统会自动使用内置轻量通道。

### 启动服务

```powershell
python run.py 127.0.0.1:8000
```

浏览器访问 <http://127.0.0.1:8000>，注册账号后即可使用。也可以只指定端口：

```powershell
python run.py 8000
```

### 验证

```powershell
Invoke-WebRequest http://127.0.0.1:8000/login -UseBasicParsing | Select-Object StatusCode
```

返回 `200` 即表示服务启动正常。

## 模型权重

仓库不包含训练权重。未放置权重时，系统自动使用内置轻量通道，页面、接口与历史记录均可正常使用，仅词级标注粒度相对较粗。

启用完整模型通道需要准备以下文件：

1. 词级权重 `deberta_CRF(new)_best.pt`，放置于项目根目录；
2. 词级基座 `microsoft/deberta-v3-base`；
3. 句级基座 `openai-community/gpt2-xl`；
4. 句级分类头 `scripts/windows_log/windows_webuse/epoch-last.pkl`。

缺少任一文件时，对应检测器会自动回退到轻量通道，不影响系统启动。具体目录结构与下载命令见 [DEPLOYMENT.md](DEPLOYMENT.md)。

## 配置项

所有配置均可通过环境变量覆盖，默认值定义于 `aigc_web/app/config.py`。

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AIGC_WEB_SECRET` | `change-this-in-production` | JWT 签名密钥，部署时必须修改 |
| `AIGC_TOKEN_EXPIRE_HOURS` | `24` | 令牌有效期（小时） |
| `AIGC_DB_PATH` | `aigc_web/aigc_web.db` | SQLite 数据库路径 |
| `WORD_MODEL_PATH` | `deberta_CRF(new)_best.pt` | 词级模型权重 |
| `WORD_MODEL_NAME` | `microsoft/deberta-v3-base` | 词级基座模型名或本地目录 |
| `AIGC_GPT2_MODEL_DIR` | `scripts/gpt2-xl` | 句级 GPT-2 目录 |
| `AIGC_SENTENCE_HEAD_DIR` | `scripts/windows_log/windows_webuse` | 句级分类头目录 |

## 接口说明

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| GET | `/login`、`/register`、`/detect`、`/history` | 否 | 页面路由 |
| POST | `/api/register` | 否 | 用户注册，返回令牌 |
| POST | `/api/login` | 否 | 用户登录，返回令牌 |
| GET | `/api/samples` | 否 | 获取内置样例 |
| POST | `/api/detect` | 是 | 文本检测 |
| POST | `/api/extract-text` | 是 | 上传文件并提取文本 |
| GET | `/api/history` | 是 | 查询历史记录（最近 100 条） |
| DELETE | `/api/history` | 是 | 清空当前用户历史记录 |

## 性能测试

使用 Apache JMeter 对检测页面进行并发测试，四档并发共完成 115 万余次请求，错误率为 0。

| 并发用户数 | 请求数 | 错误数 | 平均响应时间 | P90 | P99 | 吞吐量 |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | 293,537 | 0 | 1.88 ms | 2 ms | 3 ms | 4,895 /s |
| 20 | 288,366 | 0 | 3.48 ms | 5 ms | 5 ms | 4,806 /s |
| 50 | 293,612 | 0 | 7.70 ms | 10 ms | 76.35 ms | 4,893 /s |
| 100 | 277,707 | 0 | 14.47 ms | 21 ms | 91 ms | 4,627 /s |

检测接口在 5 千、6 万、30 万字文本下的端到端耗时分别约为 0.20 s、2.71 s 与 27.42 s，建议单次检测文本控制在 1 万字以内。完整测试说明见 [aigc_web/perf/README_perf.md](aigc_web/perf/README_perf.md)。

## 相关文档

- [部署与执行说明](DEPLOYMENT.md)
- [性能测试说明](aigc_web/perf/README_perf.md)

## 常见问题

| 现象 | 原因与处理 |
| --- | --- |
| `No module named 'fastapi'` | 未激活虚拟环境，或依赖安装到了其他 Python 解释器 |
| `No module named 'torchcrf'` | 未安装模型依赖，执行 `pip install torchcrf` |
| 启动时出现 PyTorch 相关警告 | Transformers 的版本提示，不影响系统运行 |
| 模型下载缓慢或超时 | 设置 `HF_ENDPOINT=https://hf-mirror.com` 使用国内镜像 |
| `.doc` 文件解析失败 | 本机未安装 Microsoft Word，可将文件另存为 `.docx` |
| 端口被占用 | 更换端口，例如 `python run.py 127.0.0.1:8010` |
| 页面提示 `Token expired` | 登录状态已过期，重新登录即可 |
| 长文本页面卡顿 | 建议将单次输入控制在 1 万字以内 |

## 许可证

MIT
