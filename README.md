# arcgis-dl-intel-xpu

**Unofficial Intel GPU Acceleration for ArcGIS Pro Deep Learning**

Version **0.1** · Windows · MIT

[中文](#中文说明) | [English](#english)

## 中文说明

让受支持版本的 ArcGIS Pro 原生深度学习工具尝试使用 Intel GPU。通过独立的 XPU 包覆盖层、进程内运行库配置和克隆环境中的小范围源码适配，将已覆盖的训练路径接到 PyTorch XPU。

**非 Esri、Intel 或 PyTorch 官方项目。本机测试可用，不保证稳定性、其他模型兼容性或其他电脑可用。请保留原始环境，并先用自己的数据做短程验证。**

### 本机验证和支持范围

| 项目 | 状态 |
|---|---|
| 实测电脑 | Windows 11、Intel Arc B390、ArcGIS Pro **3.4.1** |
| 安装 profile | Pro **3.4.x**、Python **3.11**、arcgis **2.4.0**、deep-learning-essentials **3.4 arcgispro_5**；4 个目标源码的 SHA-256 必须匹配 |
| XPU 后端 | PyTorch **2.14.1+xpu**、torchvision **0.29.1+xpu** |
| 已实际通过 | 本机适配环境中的原生 U-Net / ResNet34 单 batch 前向、loss、反向、参数更新和模型保存；包括软件界面启动；保存模型在 CPU 环境重载推理 |
| 尚未完成验证 | 发布安装器在干净电脑上的完整安装、修改验证集比例后的 5 轮训练及保存、长期训练、其他模型和其他 Intel GPU |
| 不支持直接安装 | Pro **3.7** 等其他版本、源码签名不匹配的环境；修改版本号不能获得兼容性 |

上述本机结果证明了适配路径可以运行，不代表所有操作都已测试。CUDA 编译的 MMCV 等扩展没有移植，不支持通用 CUDA 替换，也没有全局自动 CPU 算子回退。AMP、多 GPU 及第三方扩展不保证可用。

### 快速开始

1. 从 [Releases](https://github.com/plHXeF/arcgis-dl-intel-xpu/releases) 下载 `arcgis-dl-intel-xpu-0.1.zip`，解压到固定目录。
2. 双击 `configure.cmd`，填写 `config.local.json` 中的 ArcGIS Pro 安装目录和工程路径，保存。
3. 保存并关闭 ArcGIS Pro，双击 `start.cmd`。缺少环境时自动安装，之后只做轻量检查并打开工程。
4. 在 ArcGIS Pro 的 **Project → Package Manager** 确认活动环境为 `pro-intel-xpu`；必要时选择一次并重启。
5. 使用原生 **Train Deep Learning Model / 训练深度学习模型**，环境参数选择 **Processor Type = GPU、GPU ID = 0**，自行设置模型和训练参数并运行。

正常模式日志应显示 `device: xpu:0`、`max_batches: 0`、`mode: training`。启动器不会自动开始训练，训练轮数由原生工具参数决定。

**小数据集：** 验证集数量会向下取整。9 张切片设置 10% 会得到 0 张验证数据，出现 `validation loss = NA` 并可能在生成 EMD 时失败。可改为 **20%、batch size = 2**，输出到新的空目录。补丁会在正式 U-Net 训练前检查空训练/验证集，不会伪造数据或自动修改分割。

### 配置

```json
{
  "arcgis_pro_dir": "C:/Program Files/ArcGIS/Pro",
  "project_path": "D:/GIS/MyProject.aprx",
  "runtime_root": "%LOCALAPPDATA%/ArcGISProIntelXPU",
  "environment_name": "pro-intel-xpu",
  "source_environment": "",
  "reuse_environment": "",
  "auto_install": true
}
```

| 字段 | 含义 |
|---|---|
| `arcgis_pro_dir` | 安装根目录，应含 `bin/ArcGISPro.exe`；留空检查默认位置 |
| `project_path` | 要打开的 `.aprx`；留空只打开软件 |
| `runtime_root` | 独立的环境、缓存、日志和备份目录；建议保持默认，不要放进 Pro 安装目录 |
| `environment_name` | 新建克隆环境名，不能占用原始环境 |
| `source_environment` | 可选的未适配 ArcGIS 环境；留空使用原始 `arcgispro-py3`；来源不会被修改 |
| `reuse_environment` | 可选，明确指定已有的本补丁族 XPU 环境，跳过安装且不修改其文件；其他电脑通常留空 |
| `auto_install` | `true` 时启动自动补装；`false` 时先运行 `setup.cmd` |

相对路径以配置文件所在目录为基准；支持环境变量。JSON 路径可用 `/`，反斜杠需写成 `\\`。个人配置 `config.local.json` 不进入 Git 或发布 ZIP。

### 入口、安装与回滚

| 文件 | 用途 |
|---|---|
| `configure.cmd` | 编辑个人配置 |
| `check.cmd` | 读取路径、版本、驱动元数据和安装状态；不导入 torch、不训练 |
| `setup.cmd` | 安装缺少的环境；不启动训练 |
| `start.cmd` | 自动安装（若允许）、选择克隆并打开工程；正式训练模式 |
| `smoke.cmd` | 诊断入口；用户点击训练后限制一个 batch，不能用作正式训练 |
| `rollback.cmd` | 切回原环境，恢复本安装器管理的克隆源码和启动钩子；保留数据、环境与缓存 |

使用 ArcGIS 自带 Python/Conda，保留 pinned 依赖克隆；按需从 Esri 安装固定版本 essentials，从 PyTorch 官方 XPU 源安装固定包，并在克隆中适配 4 个签名匹配的文件。独立覆盖层保留 ArcGIS 原有 NumPy。原始环境、许可、注册表、显卡驱动和系统 DLL 不修改，运行库搜索路径只作用于当前进程。

首次安装可能下载数 GB，建议预留 **25–35 GB**。不需要额外安装 Python、Conda 或系统 oneAPI；显卡驱动需自行准备。首次安装只做一次导入与单元素 XPU 张量检查，不加载模型、不下载模型权重、不开始训练。后续启动不重复 GPU 测试。

CMD 入口不加载 `.ps1` 文件，也不修改 PowerShell 执行策略；仅用只读 PowerShell 命令解析 JSON 后调用 ArcGIS Python。若组织禁止 PowerShell 本身，仍需遵循组织策略。

日志、下载来源、安装记录、原文件备份及哈希位于 `runtime_root`。若文件已被其他软件修改，回滚会拒绝覆盖。复用外部环境时回滚仅切回原环境，不撤销外部环境补丁。不要直接复制 Conda 环境到其他电脑，应在目标机重新安装。不要自行升级适配克隆的 torch 或其他依赖。

### 构建与许可

运行 `python verify_bundle.py` 做静态检查，`python build_release.py` 生成 `dist/arcgis-dl-intel-xpu-0.1.zip` 和 SHA-256 校验文件。构建使用文件白名单，ZIP 内含逐文件哈希清单，不含个人配置、数据、模型、环境或 ArcGIS 二进制。

[MIT](LICENSE) 适用于本项目原创安装器与运行时代码；ArcGIS Pro、Esri 包及第三方依赖遵循各自许可，需由使用者自行安装和合法授权。

## English

Experimental Intel GPU support for the native deep learning tools in supported ArcGIS Pro environments. A separate XPU package overlay, process-local runtime setup and targeted patches inside a cloned environment connect the covered training path to PyTorch XPU.

**Unofficial project, unaffiliated with Esri, Intel or PyTorch. Tested to work on the development machine; stability, other models and other computers are not guaranteed. Keep the original environment and validate a short run with your own data first.**

### Tested configuration and scope

| Item | Status |
|---|---|
| Development machine | Windows 11, Intel Arc B390, ArcGIS Pro **3.4.1** |
| Installer profile | Pro **3.4.x**, Python **3.11**, arcgis **2.4.0**, deep-learning-essentials **3.4 arcgispro_5**; all four target source hashes must match |
| XPU backend | PyTorch **2.14.1+xpu**, torchvision **0.29.1+xpu** |
| Actually passed locally | Native U-Net / ResNet34 single-batch forward, loss, backward, parameter update and model saving, including a run started in the Pro UI; saved model reloaded for CPU inference |
| Not yet verified | A full clean-machine installation of this release installer; successful five-epoch training and saving after correcting the validation split; long training runs, other models and other Intel GPUs |
| Rejected by the installer | Other Pro versions, including **3.7**, or mismatched source hashes; changing a version string does not establish compatibility |

Local results establish that the adapted path can run, not that every operation has been tested. CUDA-compiled extensions such as MMCV have not been ported. This is not a universal CUDA replacement and provides no global automatic CPU operator fallback. AMP, multiple GPUs and third-party extensions are not guaranteed.

### Quick start

1. Download `arcgis-dl-intel-xpu-0.1.zip` from [Releases](https://github.com/plHXeF/arcgis-dl-intel-xpu/releases) and extract it to a permanent folder.
2. Run `configure.cmd`, enter your Pro installation and project paths in `config.local.json`, and save it.
3. Save your work and close Pro. Run `start.cmd`; missing environments are installed automatically when enabled. Subsequent launches perform lightweight checks and open the project.
4. Confirm `pro-intel-xpu` is active under **Project → Package Manager**. Select it and restart if needed.
5. Open the native **Train Deep Learning Model** tool, set **Processor Type = GPU, GPU ID = 0**, configure your model and training parameters, and run it yourself.

Normal training logs should show `device: xpu:0`, `max_batches: 0` and `mode: training`. The launcher never starts training automatically; the native tool controls the epoch count.

**Small datasets:** validation counts are rounded down. Nine chips at 10% produce an empty validation set, causing `validation loss = NA` and potentially an EMD generation failure. Try **20% validation and batch size 2**, with a new empty output folder. Formal U-Net training now checks for empty training/validation loaders before starting; it does not fabricate data or alter your split.

### Configuration

Use the JSON example in the Chinese section above; all keys are shared between languages.

| Key | Meaning |
|---|---|
| `arcgis_pro_dir` | Pro installation root containing `bin/ArcGISPro.exe`; empty uses the default location |
| `project_path` | `.aprx` to open; empty opens Pro without a project |
| `runtime_root` | Separate environments, cache, logs and backups; keep the default user directory rather than the Pro installation folder |
| `environment_name` | New clone name; must not overwrite the original environment |
| `source_environment` | Optional unpatched source environment; empty uses `arcgispro-py3`; the source is never modified |
| `reuse_environment` | Optional existing XPU environment from this patch family; skips installation and does not modify it; normally leave empty on another machine |
| `auto_install` | `true` installs missing environments on launch; with `false`, run `setup.cmd` first |

Relative paths resolve against the configuration file directory. Environment variables are expanded. Use `/` or escaped `\\` in JSON paths. Private `config.local.json` is excluded from Git and release archives.

### Commands, installation and rollback

| Entry point | Action |
|---|---|
| `configure.cmd` | Edit personal configuration |
| `check.cmd` | Read paths, versions, driver metadata and install state; no torch import or training |
| `setup.cmd` | Install missing environments; never start training |
| `start.cmd` | Install if enabled, select the clone and open the project; normal training mode |
| `smoke.cmd` | Diagnostic mode limiting a user-started training job to one batch; not normal training |
| `rollback.cmd` | Select the original environment and restore installer-owned patched sources/hooks; retain data, environments and caches |

The installer uses Pro's Python/Conda, clones with pinned dependencies, installs fixed Esri essentials and official PyTorch XPU packages as needed, and patches four files only when source hashes match. ArcGIS retains its pinned NumPy through the separate overlay. The original environment, licensing, registry, drivers and system DLLs are unchanged; runtime search paths are process-local.

A fresh setup can download several GB; allow about **25–35 GB** of space. No separate Python, Conda or system oneAPI installation is required. Prepare a supported Intel GPU driver yourself. The first installation performs one import/tiny XPU tensor health check, without loading a model, downloading model weights or training. Later launches do not repeat GPU probes.

CMD launchers do not load `.ps1` files or change PowerShell execution policy. A read-only PowerShell command parses JSON before invoking Pro's Python. If PowerShell itself is prohibited by your organization, its policies still apply.

Logs, dependency provenance, installation records, source backups and hashes live under `runtime_root`. Rollback refuses to overwrite files changed by other software. In external-environment reuse mode, rollback only selects the original environment; it does not undo that external environment's patches. Reinstall on each target computer instead of copying Conda environments. Avoid independently upgrading dependencies in the adapted clone.

### Build and license

Run `python verify_bundle.py` for static validation, then `python build_release.py` to produce `dist/arcgis-dl-intel-xpu-0.1.zip` and its SHA-256 checksum. Packaging uses an explicit file allowlist and includes per-file hashes. Personal configuration, datasets, models, environments and ArcGIS binaries are excluded.

[MIT](LICENSE) covers this project's original installer/runtime code. ArcGIS Pro, Esri packages and third-party dependencies retain their own licenses and must be installed and licensed separately.

## Official references / 官方参考

- [Esri deep-learning-frameworks](https://github.com/Esri/deep-learning-frameworks)
- [Esri raster-deep-learning](https://github.com/Esri/raster-deep-learning)
- [PyTorch Intel GPU / XPU](https://docs.pytorch.org/docs/main/notes/get_start_xpu.html)
- [Intel GPU prerequisites](https://www.intel.com/content/www/us/en/developer/articles/tool/pytorch-prerequisites-for-intel-gpu.html)
- [Unified Runtime adapter loading](https://oneapi-src.github.io/unified-runtime/core/INTRO.html)
