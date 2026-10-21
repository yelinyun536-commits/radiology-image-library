# 医学影像学图像库（Radiology Image Library）

946 张医学影像 + 44 种疾病知识卡片，全部来自 CC BY 4.0 开源数据集，可离线浏览。

## 快速使用

1. 下载：到本仓库 [Releases 页面](../../releases) 下载 `radiology-image-library.zip`（约 59MB），或直接 `git clone` 本仓库
2. 解压后双击 `index.html` 即可在浏览器离线浏览（无需联网、无需服务器）

## 内容概览

| 项目 | 数量 |
|---|---|
| 影像总数 | 946 |
| 成像模态 | 7 种：CT 516 / X-Ray 161 / MRI 133 / OCT 60 / 皮肤镜 35 / 眼底 25 / 超声 16 |
| 疾病种类 | 44 种，均含症状 / 描述 / 病因 / 治疗 / 预防知识卡片 |

每张影像均标注：**相关症状 / 解剖位置 / 知识点 / 模态 / 疾病卡片**。

## 目录结构

```
├── index.html        离线浏览页面（自包含）
├── images/           946 张影像，按模态分目录（CT / MRI / XRay / OCT / Fundus / Dermoscopy / Ultrasound）
├── metadata/
│   ├── library.json          主索引（每张图片一条记录）
│   ├── library.csv           扁平表格（Excel 可打开）
│   └── knowledge_base.json   疾病 / 检查方式知识卡片
└── scripts/          构建脚本（留档）
```

## 数据来源（均为 CC BY 4.0）

- SLAKE（Bo-Li-Lab/SLAKE）：CT / MRI / X-Ray 双语问答数据集
- MedMNIST：BreastMNIST、PneumoniaMNIST、DermaMNIST、ChestMNIST、RetinaMNIST、FractureMNIST3D、OrganCMNIST、NoduleMNIST3D
- Kermany2018 OCT（HuggingFace）：视网膜 OCT 四分类
- Brain Tumor MRI Dataset：脑肿瘤 MRI 四分类

## 完整性校验

`radiology-image-library.zip`：

- SHA-256：`69e5b204dead82b11c83aab67b1bbd22ed174676b717027acdfca2abd5f3e0e6`
- MD5：`1d45a677173916cf09c84ea851adea36`
