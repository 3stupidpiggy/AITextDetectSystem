# 部署与执行说明

下面说明 AI 文本检测系统的环境准备、依赖安装、启动方式、模型配置与生产部署建议。系统开发和测试环境为 Windows 11 + Python 3.9.23，Linux 与 macOS 下同样可以运行，仅 `.doc` 文件解析依赖本机安装 Microsoft Word。

## 一、环境要求

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Windows 10 / 11；Linux、macOS 可运行 |
| Python | 3.9 ~ 3.12（在 3.9.23 上完成验证） |
| 内存 | 建议 8 GB 及以上 |
| 磁盘 | 不含模型约 100 MB；含基座模型约 7 GB |
| GPU | 可选。NVIDIA GPU + CUDA 可加速模型通道 |
| 浏览器 | Chrome、Edge 等 Chromium 内核浏览器 |
| 办公软件 | 解析 `.doc` 时需要安装 Microsoft Word |

## 二、依赖安装

### 2.1 创建虚拟环境

```powershell
cd G:\project\NetRace\web
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
```

也可以使用 conda：

```powershell
conda create -n aigc-web python=3.11 -y
conda activate aigc-web
```

### 2.2 安装 Web 依赖

```powershell
python -m pip install -r requirements.txt
```

`requirements.txt` 默认启用 Web 框架、模板、数据校验与文档解析相关依赖，模型推理部分默认注释。国内网络环境可使用镜像：

```powershell
python -m pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 2.3 安装模型依赖（可选）

需要启用模型通道时，取消 `requirements.txt` 中模型推理部分的注释后重新安装，或直接执行：

```powershell
python -m pip install numpy torch "transformers>=4.36,<5.0" torchcrf sentencepiece
```

GPU 版本请根据本机 CUDA 版本选择对应的 PyTorch 安装命令。

## 三、启动与验证

### 3.1 启动命令

```powershell
python run.py 127.0.0.1:8000
```

启动脚本会自动把 `aigc_web` 加入模块搜索路径，无需额外指定 `--app-dir`。

| 命令 | 说明 |
| --- | --- |
| `python run.py` | 默认监听 `127.0.0.1:8000` |
| `python run.py 8000` | 仅指定端口，地址默认为 `127.0.0.1` |
| `python run.py 127.0.0.1:8010` | 指定地址与端口 |
| `python run.py 0.0.0.0:8000` | 允许局域网访问 |
| `python run.py 127.0.0.1:8010 --reload` | 开发模式，代码变更自动重载 |

### 3.2 服务验证

```powershell
Invoke-WebRequest http://127.0.0.1:8000/login -UseBasicParsing | Select-Object StatusCode
Invoke-RestMethod http://127.0.0.1:8000/api/samples | Measure-Object
```

登录页返回 `200`、样例接口返回 5 条记录，说明服务启动正常。

### 3.3 接口冒烟测试

```powershell
$body = @{ username = "demo"; password = "demo123456" } | ConvertTo-Json
$token = (Invoke-RestMethod -Uri http://127.0.0.1:8000/api/register -Method Post -ContentType "application/json" -Body $body).token
$headers = @{ Authorization = "Bearer $token" }
$detect = @{ text = "这是一段用于测试的文本。" } | ConvertTo-Json
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/detect -Method Post -Headers $headers -ContentType "application/json" -Body $detect
```

### 3.4 停止服务

在运行窗口按 `Ctrl + C` 即可停止。

## 四、模型准备（可选）

系统未检测到模型权重时，会自动使用内置轻量通道，页面与接口均可正常使用。以下步骤仅在需要启用完整模型通道时执行。

### 4.1 下载基座模型

```powershell
python -m pip install -U huggingface_hub
$env:HF_ENDPOINT = "https://hf-mirror.com"

huggingface-cli download microsoft/deberta-v3-base --local-dir scripts/deberta-v3-base
huggingface-cli download openai-community/gpt2-xl --local-dir scripts/gpt2-xl
```

`huggingface_hub` 新版命令为 `hf download`，与 `huggingface-cli download` 等价。也可以不下载到本地，直接使用模型名，由 Transformers 自动缓存。

### 4.2 准备模型文件

```
web/
├── deberta_CRF(new)_best.pt          # 词级 CRF 权重
└── scripts/
    ├── deberta-v3-base/              # 词级基座
    ├── gpt2-xl/                      # 句级 GPT-2
    └── windows_log/windows_webuse/   # 句级分类头（epoch-last.pkl）
```

句级外部后端需要 `scripts/gpt2-xl` 与 `scripts/windows_log/windows_webuse` 两个目录同时存在，否则句子级检测使用内置通道。以上路径均可通过环境变量覆盖。

### 4.3 模型通道说明

模型加载在应用进程内完成，首次启动时会读取本地权重并初始化推理环境。若权重缺失、路径错误或依赖不完整，系统会记录原因并自动回退，不会导致启动失败。

## 五、配置说明

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AIGC_WEB_SECRET` | `change-this-in-production` | JWT 签名密钥，部署时必须修改 |
| `AIGC_TOKEN_EXPIRE_HOURS` | `24` | 令牌有效期（小时），演示环境可适当调大 |
| `AIGC_DB_PATH` | `aigc_web/aigc_web.db` | SQLite 数据库路径 |
| `WORD_MODEL_PATH` | `deberta_CRF(new)_best.pt` | 词级模型权重路径 |
| `WORD_MODEL_NAME` | `microsoft/deberta-v3-base` | 词级基座模型名或本地目录 |
| `AIGC_GPT2_MODEL_DIR` | `scripts/gpt2-xl` | 句级 GPT-2 目录 |
| `AIGC_SENTENCE_HEAD_DIR` | `scripts/windows_log/windows_webuse` | 句级分类头目录 |

PowerShell 配置示例：

```powershell
$env:AIGC_WEB_SECRET = "please-change-me"
$env:AIGC_TOKEN_EXPIRE_HOURS = "720"
$env:WORD_MODEL_NAME = "scripts/deberta-v3-base"
```

环境变量仅在当前终端会话内生效，重新打开终端后需要重新设置。

## 六、生产部署建议

1. **单进程运行**：模型加载在进程内，多 worker 会重复占用显存与内存，建议使用单进程部署。
2. **修改签名密钥**：`AIGC_WEB_SECRET` 必须替换为随机字符串，避免令牌被伪造。
3. **反向代理与 HTTPS**：使用 Nginx 或 Caddy 处理 TLS 与静态资源缓存，对外仅暴露代理端口。
4. **关闭热重载**：生产环境不要使用 `--reload`。
5. **限制访问来源**：如无公开访问需求，可通过安全组或网关限制来源 IP。
6. **日志与监控**：保留 Uvicorn 访问日志，关注 401、400 与 5xx 响应比例。

## 七、数据管理

数据库默认位于 `aigc_web/aigc_web.db`，首次启动时自动建表，保存用户信息与检测记录。

- **备份**：停止服务后直接复制该文件；
- **恢复**：将备份文件覆盖回原路径，重启服务即可；
- **迁移**：同时迁移数据库文件与模型权重目录，保持相对路径一致。

## 八、常见问题

| 现象 | 原因与处理 |
| --- | --- |
| `ModuleNotFoundError: No module named 'fastapi'` | 未激活虚拟环境，或依赖安装到了其他 Python 解释器 |
| `No module named 'torchcrf'` | 未安装模型依赖，执行 `python -m pip install torchcrf` |
| 启动时提示 PyTorch 相关警告 | Transformers 的版本提示，不影响系统运行 |
| 模型下载缓慢或超时 | 设置 `HF_ENDPOINT=https://hf-mirror.com`，或手动下载后指定本地目录 |
| `.doc` 文件解析失败 | 本机未安装 Microsoft Word，可先将文件另存为 `.docx` |
| 端口被占用 | 更换端口，例如 `python run.py 127.0.0.1:8010` |
| 页面提示 `Token expired` | 登录状态超过有效期，退出后重新登录 |
| 长文本页面卡顿 | 建议将单次输入控制在 1 万字以内 |
| 上传大文件响应缓慢 | 文件会整体读入内存，建议单个文件不超过几十 MB |

## 九、目录说明

```
web/
├── aigc_web/          # 应用代码、模板、静态资源与压测材料
├── scripts/           # 模型推理脚本与权重目录
├── run.py             # 启动入口
├── requirements.txt   # 依赖清单
├── README.md          # 项目说明
└── DEPLOYMENT.md      # 部署说明
```
