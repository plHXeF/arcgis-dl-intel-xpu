# 0.1

Unofficial Intel GPU Acceleration for ArcGIS Pro Deep Learning

## 中文

- 首个公开版本：配置 ArcGIS Pro / APRX 路径，检查并按需安装环境，通过原生深度学习工具使用 Intel XPU。
- 正式启动不限制 batch；诊断入口单独提供一个 batch 的验证模式。
- 提供空训练/验证集预检查、源码签名校验、备份和回滚，中英双语说明，MIT 许可。
- 本机 Windows 11 / ArcGIS Pro 3.4.1 / Arc B390 已通过原生 U-Net 单 batch 训练、参数更新和保存。完整训练、干净电脑安装及其他模型尚未完成验证，不保证稳定性。
- 仅支持匹配源码签名的 Pro 3.4 profile；不支持直接用于 Pro 3.7。

下载 `arcgis-dl-intel-xpu-0.1.zip`，解压后运行 `configure.cmd`，关闭 Pro 后运行 `start.cmd`。ZIP 不包含 ArcGIS、环境、模型、数据或本机配置。校验文件与 ZIP 一并提供。

## English

- First public release: configurable Pro / APRX paths, environment checks and installation as needed, and Intel XPU integration with native deep learning tools.
- Normal launches do not impose a batch limit; a separate diagnostic launcher limits user-started training to one batch.
- Includes empty-loader preflight checks, source signature checks, backups, rollback, bilingual documentation and the MIT license.
- Native U-Net single-batch training, parameter updates and saving passed locally on Windows 11 / Pro 3.4.1 / Arc B390. Full training, clean-machine installation and other models remain unverified. Stability is not guaranteed.
- Supports only the Pro 3.4 profile with matching source hashes, not Pro 3.7.

Download and extract `arcgis-dl-intel-xpu-0.1.zip`, run `configure.cmd`, close Pro, then run `start.cmd`. ArcGIS, environments, models, datasets and personal configuration are excluded. A SHA-256 checksum is provided alongside the archive.
