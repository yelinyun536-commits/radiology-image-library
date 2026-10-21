#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
医学影像学图像库构建脚本
=========================
数据源（均来自 GitHub 上调研选定的开源项目）:
  1. SLAKE  (GitHub: Bo-Li-Lab/SLAKE, HuggingFace: BoKelvin/SLAKE, CC BY 4.0)
     642 张放射影像 (CT / MRI / X-Ray) + 14,028 条中英双语问答 + 中英文医学知识库
  2. MedMNIST (GitHub: MedMNIST/MedMNIST, Zenodo: 10.5281/zenodo.10519652, CC BY 4.0)
     BreastMNIST 乳腺超声、PneumoniaMNIST 儿童胸部 X 线肺炎

功能: 为每张图片确定 —— 相关症状 / 解剖位置 / 知识点，并生成:
  - images/            按成像模态组织的图像文件
  - metadata/library.json        图像库主索引（每张图片一条记录）
  - metadata/library.csv         扁平表格（便于 Excel 查看）
  - metadata/knowledge_base.json 疾病/检查方式知识库卡片
  - index.html                   本地浏览页面（可直接双击打开）

用法: python3 build_library.py
依赖: numpy, Pillow
"""
import csv
import json
import os
import re
import shutil
from collections import Counter, defaultdict

import numpy as np
from PIL import Image

CACHE = "/workspace/.cache"
SLAKE_DIR = os.path.join(CACHE, "slake")
MEDMNIST_DIR = os.path.join(CACHE, "medmnist")
OUT = "/workspace/radiology-image-library"

SLAKE_URL = "https://huggingface.co/datasets/BoKelvin/SLAKE"
MEDMNIST_URL = "https://github.com/MedMNIST/MedMNIST"

# ---------------------------------------------------------------- 中文映射
LOC_ZH = {
    "Lung": "胸部（肺）",
    "Chest_lung": "胸部（肺）",
    "Chest_heart": "胸部（心脏）",
    "Chest_mediastinal": "胸部（纵隔）",
    "Abdomen": "腹部",
    "Brain": "头部（脑）",
    "Brain_Tissue": "头部（脑组织）",
    "Brain_Face": "头部（颅面）",
    "Neck": "颈部",
    "Pelvic Cavity": "盆腔",
}

MODALITY_ZH = {
    "CT": "CT（计算机断层扫描）",
    "MRI": "MRI（磁共振成像）",
    "X-Ray": "X 线摄影",
    "Ultrasound": "超声成像",
    "OCT": "OCT（光学相干断层扫描）",
    "Fundus": "眼底摄影",
    "Dermoscopy": "皮肤镜检查",
}

ORGAN_ZH = {
    "liver": "肝脏", "kidney": "肾脏", "spleen": "脾脏", "lung": "肺",
    "heart": "心脏", "brain": "脑", "stomach": "胃", "bladder": "膀胱",
    "uterus": "子宫", "intestine": "肠", "bone": "骨骼", "spine": "脊柱",
    "rib": "肋骨", "breast": "乳腺", "thyroid": "甲状腺", "eye": "眼球",
    "skin": "皮肤", "muscle": "肌肉", "aorta": "主动脉",
}

# 中文器官名归一化为英文键（避免中英文问答重复计数）
ZH_ORGAN_TO_EN = {
    "肝脏": "liver", "肾脏": "kidney", "脾脏": "spleen", "肺": "lung",
    "心脏": "heart", "脑": "brain", "胃": "stomach", "膀胱": "bladder",
    "子宫": "uterus", "肠": "intestine", "骨": "bone", "脊柱": "spine",
    "乳腺": "breast", "甲状腺": "thyroid", "眼球": "eye", "皮肤": "skin",
    "肌肉": "muscle", "主动脉": "aorta",
}

# 疾病答案规范化（SLAKE 标注中的拼写变体）
DISEASE_ALIAS = {
    "Noudle": "Nodule",
    "Cardiomegal": "Cardiomegaly",
    "Cardiomega": "Cardiomegaly",
    "Brian Edema": "Brain Edema",
}

# 英文疾病 -> 知识卡片 ID
DISEASE_CARD_ID = {
    "Brain Edema": "brain_edema",
    "Liver Cancer": "liver_cancer",
    "Cardiomegaly": "cardiomegaly",
    "Brain Tumor": "brain_tumor",
    "Lung Cancer": "lung_cancer",
    "Atelectasis": "atelectasis",
    "Brain Enhancing Tumor": "brain_enhancing_tumor",
    "Brain Non-enhancing Tumor": "brain_non_enhancing_tumor",
    "Nodule": "nodule",
    "Pneumonia": "pneumonia",
    "Pneumothorax": "pneumothorax",
    "Mass": "mass",
    "Effusion": "effusion",
    "Infiltration": "infiltration",
    "Pulmonary Mass": "pulmonary_mass",
    "Pleural Effusion": "pleural_effusion",
    "Pulmonary Infiltration": "pulmonary_infiltration",
    "Pulmonary Nodule": "pulmonary_nodule",
    "Kidney Cancer": "kidney_cancer",
    "Breast Cancer": "breast_cancer",
    "Breast Benign Lesion": "breast_benign",
    "CNV": "cnv",
    "DME": "dme",
    "DRUSEN": "drusen",
    "Glioma": "glioma",
    "Meningioma": "meningioma",
    "Pituitary Tumor": "pituitary_tumor",
    "Diabetic Retinopathy": "diabetic_retinopathy",
    "Buckle Rib Fracture": "rib_fracture_buckle",
    "Nondisplaced Rib Fracture": "rib_fracture_nondisplaced",
    "Displaced Rib Fracture": "rib_fracture_displaced",
    "Actinic Keratosis": "actinic_keratosis",
    "Basal Cell Carcinoma": "basal_cell_carcinoma",
    "Benign Keratosis": "benign_keratosis",
    "Dermatofibroma": "dermatofibroma",
    "Melanoma": "melanoma",
    "Melanocytic Nevus": "melanocytic_nevus",
    "Vascular Lesion": "vascular_lesion",
    "Consolidation": "consolidation",
    "Pulmonary Edema": "pulmonary_edema",
    "Emphysema": "emphysema",
    "Pulmonary Fibrosis": "pulmonary_fibrosis",
    "Pleural Thickening": "pleural_thickening",
    "Diaphragmatic Hernia": "diaphragmatic_hernia",
}

DISEASE_ZH_FALLBACK = {
    "Brain Edema": "脑水肿", "Liver Cancer": "肝癌", "Cardiomegaly": "心脏增大",
    "Brain Tumor": "脑肿瘤", "Lung Cancer": "肺癌", "Atelectasis": "肺不张",
    "Brain Enhancing Tumor": "脑肿瘤（强化型）",
    "Brain Non-enhancing Tumor": "脑肿瘤（非强化型）",
    "Nodule": "结节", "Pneumonia": "肺炎", "Pneumothorax": "气胸",
    "Mass": "肿块", "Effusion": "积液", "Infiltration": "浸润影",
    "Pulmonary Mass": "肺肿块", "Pleural Effusion": "胸腔积液",
    "Pulmonary Infiltration": "肺浸润", "Pulmonary Nodule": "肺结节",
    "Kidney Cancer": "肾癌", "Breast Cancer": "乳腺癌",
    "Breast Benign Lesion": "乳腺良性病变",
    "CNV": "脉络膜新生血管（CNV）", "DME": "糖尿病黄斑水肿（DME）",
    "DRUSEN": "玻璃膜疣（Drusen）", "Glioma": "胶质瘤",
    "Meningioma": "脑膜瘤", "Pituitary Tumor": "垂体瘤",
    "Diabetic Retinopathy": "糖尿病视网膜病变",
    "Buckle Rib Fracture": "肋骨骨折（青枝/弯曲型）",
    "Nondisplaced Rib Fracture": "肋骨骨折（无移位）",
    "Displaced Rib Fracture": "肋骨骨折（移位）",
    "Actinic Keratosis": "光化性角化病",
    "Basal Cell Carcinoma": "基底细胞癌",
    "Benign Keratosis": "良性角化病（脂溢性角化等）",
    "Dermatofibroma": "皮肤纤维瘤",
    "Melanoma": "恶性黑色素瘤",
    "Melanocytic Nevus": "色素痣",
    "Vascular Lesion": "血管性皮肤病变",
    "Consolidation": "肺实变",
    "Pulmonary Edema": "肺水肿",
    "Emphysema": "肺气肿",
    "Pulmonary Fibrosis": "肺纤维化",
    "Pleural Thickening": "胸膜增厚",
    "Diaphragmatic Hernia": "膈疝",
}

# ------------------------------------------------- 补充知识卡片（知识库未覆盖者，人工编写）
SUPPLEMENT_CARDS = {
    "brain_tumor": {
        "name_zh": "脑肿瘤",
        "symptoms": ["头痛", "恶心呕吐", "视物模糊", "肢体无力", "癫痫发作", "认知功能下降"],
        "description": "颅内占位性病变，分良性和恶性。MRI 是脑肿瘤最重要的影像学检查，可显示肿瘤部位、大小、水肿及与周围结构的关系。",
        "cause": "病因尚不完全明确，可能与遗传易感、电离辐射暴露等有关",
        "treatment": "以手术切除为主，辅以放疗、化疗及靶向治疗",
        "prevention": "避免不必要的电离辐射暴露；出现进行性头痛、神经功能缺损时及时就诊",
    },
    "brain_enhancing_tumor": {
        "name_zh": "脑肿瘤（强化型）",
        "symptoms": ["头痛", "恶心呕吐", "肢体无力", "癫痫发作"],
        "description": "增强 MRI 上明显强化的脑肿瘤，提示血脑屏障破坏，常见于高级别胶质瘤、转移瘤、脑膜瘤等，通常恶性程度较高。",
        "cause": "肿瘤新生血管丰富、血脑屏障破坏导致对比剂渗出",
        "treatment": "手术切除为主，辅以放疗、化疗",
        "prevention": "定期体检，神经系统症状出现时尽早行增强 MRI 检查",
    },
    "brain_non_enhancing_tumor": {
        "name_zh": "脑肿瘤（非强化型）",
        "symptoms": ["头痛", "癫痫发作", "认知功能下降"],
        "description": "增强 MRI 上无明显强化的脑肿瘤，常见于低级别胶质瘤，血脑屏障相对完整，生长较缓慢。",
        "cause": "肿瘤分化较好、血脑屏障破坏轻",
        "treatment": "手术切除，部分需术后放疗/化疗并长期随访",
        "prevention": "癫痫或进行性神经症状患者应行 MRI 筛查",
    },
    "nodule": {
        "name_zh": "结节",
        "symptoms": ["多无明显症状", "偶见咳嗽、胸闷（肺结节较大时）"],
        "description": "影像学上直径 ≤3 cm 的类圆形或不规则形局灶性病变。大多数结节为良性（炎症、瘢痕等），需结合大小、形态（分叶、毛刺、磨玻璃成分）及随访变化评估恶性风险。",
        "cause": "炎症、感染后瘢痕、良性增生或早期肿瘤等",
        "treatment": "以定期影像随访为主；高危结节可行增强 CT、PET-CT 或活检",
        "prevention": "高危人群（长期吸烟等）定期低剂量 CT 筛查",
    },
    "pulmonary_nodule": {
        "name_zh": "肺结节",
        "symptoms": ["多无明显症状", "咳嗽", "偶见痰中带血"],
        "description": "肺内直径 ≤3 cm 的局灶性病变，CT 是检出和评估的首选方法。按密度分为实性、部分实性（混合磨玻璃）和纯磨玻璃结节；直径越大、边缘毛刺/分叶越明显，恶性可能越高。",
        "cause": "感染后瘢痕、肉芽肿、局灶性出血或早期肺癌等",
        "treatment": "低危者定期 CT 随访；高度怀疑恶性者手术切除或立体定向放疗",
        "prevention": "戒烟，避免粉尘及二手烟暴露，高危人群定期筛查",
    },
    "mass": {
        "name_zh": "肿块",
        "symptoms": ["局部占位效应引起的压迫症状", "疼痛", "体重下降（恶性时）"],
        "description": "影像学上直径 >3 cm 的占位性病变，需鉴别良恶性。增强 CT/MRI 可评估血供与侵犯范围，确诊依赖病理活检。",
        "cause": "良性肿瘤、恶性肿瘤、炎性假瘤、脓肿等",
        "treatment": "根据性质选择手术、放化疗或抗感染治疗",
        "prevention": "发现肿块后尽早完善增强影像与病理检查",
    },
    "effusion": {
        "name_zh": "积液",
        "symptoms": ["胸闷", "呼吸困难（量多时）", "原发病表现"],
        "description": "体腔内异常积聚的液体，以胸腔积液最常见。X 线/CT 表现为肋膈角变钝或水样密度影，超声可定位并引导穿刺。",
        "cause": "感染、肿瘤、心力衰竭、低蛋白血症、自身免疫病等",
        "treatment": "针对病因治疗；量大或有症状时穿刺引流",
        "prevention": "积极治疗原发病",
    },
    "infiltration": {
        "name_zh": "浸润影",
        "symptoms": ["咳嗽", "咳痰", "发热（感染性时）"],
        "description": "异常物质（炎性渗出液、肿瘤细胞等）在组织间隙内弥漫沉积形成的影像表现，边界多不清楚。肺部浸润常见于肺炎、肺结核、肺水肿等。",
        "cause": "感染、炎症、肿瘤浸润、肺水肿等",
        "treatment": "针对病因：抗感染、抗肿瘤或纠正心衰等",
        "prevention": "增强体质，呼吸道感染及时治疗",
    },
    "kidney_cancer": {
        "name_zh": "肾癌",
        "symptoms": ["无痛性肉眼血尿", "腰痛", "腹部包块（三联征，晚期）", "多数早期无症状"],
        "description": "肾脏恶性肿瘤，以肾细胞癌最常见。多数为体检超声偶然发现；CT 增强扫描是诊断和分期的主要方法，典型表现为富血供强化肿块。",
        "cause": "吸烟、肥胖、高血压、长期透析及遗传因素等",
        "treatment": "局限性肾癌以手术（根治性/保留肾单位切除）为主；晚期可用靶向与免疫治疗",
        "prevention": "戒烟、控制体重，定期体检行肾脏超声",
    },
    "breast_cancer": {
        "name_zh": "乳腺癌",
        "symptoms": ["无痛性乳房肿块", "皮肤凹陷或橘皮样改变", "乳头溢液", "腋窝淋巴结肿大"],
        "description": "乳腺上皮来源的恶性肿瘤。超声表现为形态不规则、边界不清的低回声结节，可伴微钙化与血流丰富；确诊需结合钼靶、MRI 及穿刺活检（BI-RADS 分级评估）。",
        "cause": "激素水平、遗传（BRCA1/2 突变）、肥胖、饮酒等",
        "treatment": "手术为主，辅以放疗、化疗、内分泌及靶向治疗",
        "prevention": "定期乳腺超声/钼靶筛查，保持健康生活方式",
    },
    "breast_benign": {
        "name_zh": "乳腺良性病变",
        "symptoms": ["乳房肿块（多无痛）", "周期性胀痛（增生时）"],
        "description": "包括纤维腺瘤、囊肿、乳腺增生等。超声多表现为边界清楚、形态规则、活动度好的结节，BI-RADS 1-3 级，恶性风险低。",
        "cause": "激素水平波动、乳腺组织增生等",
        "treatment": "定期随访观察；较大或有症状者可手术切除",
        "prevention": "规律作息，避免外源性激素滥用，定期乳腺检查",
    },
    "cnv": {
        "name_zh": "脉络膜新生血管（CNV）",
        "symptoms": ["视力下降", "视物变形", "中心暗点", "视物变小"],
        "description": "脉络膜来源的新生血管经 Bruch 膜破口长入视网膜下，常见于湿性年龄相关性黄斑变性、病理性近视等。OCT 表现为 RPE 层下高信号病灶，常伴视网膜下液/视网膜内液。",
        "cause": "湿性年龄相关性黄斑变性、病理性近视、炎症等",
        "treatment": "玻璃体腔注射抗 VEGF 药物为首选；亦可行光动力治疗（PDT）",
        "prevention": "老年人定期眼底/OCT 筛查，阿姆斯勒方格表自查",
    },
    "dme": {
        "name_zh": "糖尿病黄斑水肿（DME）",
        "symptoms": ["视力下降", "视物变形", "阅读困难"],
        "description": "糖尿病导致视网膜毛细血管受损、通透性增加，液体积聚于黄斑区。OCT 可见视网膜内囊样低信号腔隙与视网膜增厚，是糖尿病患者视力下降最常见的原因。",
        "cause": "长期高血糖损伤视网膜微血管",
        "treatment": "玻璃体腔注射抗 VEGF/糖皮质激素、激光光凝，并控制血糖",
        "prevention": "糖尿病患者每年至少一次散瞳眼底检查",
    },
    "drusen": {
        "name_zh": "玻璃膜疣（Drusen）",
        "symptoms": ["多无症状", "融合增大时轻度中心视力下降"],
        "description": "位于视网膜色素上皮层与 Bruch 膜之间的局灶性沉积物，OCT 表现为 RPE 层下丘状高信号隆起，是年龄相关性黄斑变性（干性）的早期特征性表现。",
        "cause": "年龄、代谢、遗传因素",
        "treatment": "早期无需治疗；中期可补充 AREDS 抗氧化维生素配方延缓进展",
        "prevention": "戒烟、防晒、定期 OCT 随访监测向湿性转化",
    },
    "glioma": {
        "name_zh": "胶质瘤",
        "symptoms": ["头痛", "恶心呕吐", "癫痫发作", "进行性肢体无力", "人格改变"],
        "description": "颅内最常见的原发性恶性肿瘤，起源于神经胶质细胞，按 WHO 分为 1-4 级，胶质母细胞瘤（GBM）恶性程度最高。MRI 常表现为混杂信号占位伴水肿与占位效应，增强可呈环形强化。",
        "cause": "病因不明，与基因突变（IDH 等）、电离辐射暴露相关",
        "treatment": "最大安全范围手术切除 + 放疗 + 化疗（替莫唑胺）",
        "prevention": "无特异性预防；进行性头痛、神经功能缺损应尽早行 MRI 检查",
    },
    "meningioma": {
        "name_zh": "脑膜瘤",
        "symptoms": ["头痛", "癫痫发作", "局灶性神经功能缺损（与部位相关）", "多无症状偶然发现"],
        "description": "起源于蛛网膜帽状细胞的颅内肿瘤，多为良性，约占颅内肿瘤的 30%。MRI 表现为宽基底附着于硬膜、边界清楚、均匀明显强化的肿块，可见特征性“硬膜尾征”。",
        "cause": "与女性激素、放射线暴露、2 型神经纤维瘤病等相关",
        "treatment": "手术切除为首选；小而无症状者可随访；可辅以放疗/伽玛刀",
        "prevention": "定期随访，有家族史者建议筛查",
    },
    "pituitary_tumor": {
        "name_zh": "垂体瘤",
        "symptoms": ["头痛", "视野缺损（双颞侧偏盲）", "内分泌紊乱（泌乳、闭经、肢端肥大等）"],
        "description": "起源于垂体前叶的常见颅内良性肿瘤，分为功能性（泌乳素瘤、生长激素瘤等）与无功能性。MRI 表现为鞍区占位，大腺瘤可向上压迫视交叉呈“雪人征”。",
        "cause": "多为散发，部分与遗传综合征（MEN1 等）相关",
        "treatment": "泌乳素瘤首选药物（多巴胺受体激动剂）；其余多经蝶窦手术切除",
        "prevention": "出现月经紊乱、泌乳、视野缺损时行鞍区 MRI 与内分泌检查",
    },
    "diabetic_retinopathy": {
        "name_zh": "糖尿病视网膜病变",
        "symptoms": ["早期多无症状", "视物模糊", "飞蚊症", "视野缺损", "晚期严重视力下降"],
        "description": "糖尿病引起的视网膜微血管损害，分为非增殖性（NPDR，轻/中/重度）与增殖性（PDR）。眼底可见微动脉瘤、点片状出血、硬性渗出、棉絮斑及新生血管，是工作年龄人群致盲的主要原因之一。",
        "cause": "长期高血糖损伤视网膜毛细血管周细胞与内皮细胞",
        "treatment": "视网膜激光光凝、玻璃体腔抗 VEGF 注射、玻璃体切割术；严格控制血糖/血压/血脂是基础",
        "prevention": "2 型糖尿病确诊后即应进行全面眼底检查，此后每年至少一次",
    },
    "rib_fracture_buckle": {
        "name_zh": "肋骨骨折（青枝/弯曲型）",
        "symptoms": ["局部胸壁疼痛", "压痛", "深呼吸或咳嗽时疼痛加重"],
        "description": "肋骨皮质皱褶、弯曲但连续性未完全中断的稳定性骨折，常见于儿童及低能量损伤。CT 表现为肋骨皮质局部皱褶、成角。",
        "cause": "胸部直接/间接暴力外伤",
        "treatment": "镇痛、胸带固定、对症治疗；警惕气胸等并发症",
        "prevention": "防止跌倒、运动防护",
    },
    "rib_fracture_nondisplaced": {
        "name_zh": "肋骨骨折（无移位）",
        "symptoms": ["局部胸壁疼痛", "压痛", "深呼吸或咳嗽时疼痛加重"],
        "description": "肋骨皮质连续性中断但断端无明显移位，CT 可见线样低密度影贯穿肋骨皮质，是胸部外伤最常见的骨折类型。",
        "cause": "胸壁外伤、剧烈咳嗽、病理性骨折（肿瘤转移、骨质疏松）",
        "treatment": "镇痛、固定、防治肺部并发症；多发骨折需评估连枷胸",
        "prevention": "防跌倒、治疗原发骨病",
    },
    "rib_fracture_displaced": {
        "name_zh": "肋骨骨折（移位）",
        "symptoms": ["剧烈胸壁疼痛", "反常呼吸（连枷胸）", "呼吸困难", "皮下气肿"],
        "description": "肋骨断端移位，可损伤胸膜、肺组织及肋间血管，常合并血气胸。CT 显示肋骨连续性中断伴断端错位及周围软组织肿胀。",
        "cause": "高能量胸部创伤（车祸、坠落）",
        "treatment": "固定、血气胸闭式引流、必要时手术内固定与呼吸支持",
        "prevention": "交通安全、高空作业防护",
    },
    "actinic_keratosis": {
        "name_zh": "光化性角化病",
        "symptoms": ["皮肤粗糙鳞屑性斑疹", "触之砂纸感", "轻度瘙痒或触痛", "日晒部位多发"],
        "description": "长期日光损伤引起的表皮角质形成细胞异常增生，好发于头面、手背等曝光部位，皮肤镜下可见草莓样模式（红色假网状血管伴毛囊开口周围白晕）。属于癌前病变，部分可进展为鳞状细胞癌。",
        "cause": "长期紫外线（日光）暴露",
        "treatment": "冷冻治疗、外用 5-氟尿嘧啶/咪喹莫特、光动力治疗",
        "prevention": "防晒（防晒霜、遮阳），定期皮肤检查",
    },
    "basal_cell_carcinoma": {
        "name_zh": "基底细胞癌",
        "symptoms": ["珍珠样半透明丘疹或结节", "表面毛细血管扩张", "易破溃出血、溃疡不愈", "生长缓慢"],
        "description": "最常见的皮肤恶性肿瘤，起源于表皮基底层，好发于头面部，恶性度低、极少转移但可局部侵袭破坏。皮肤镜典型表现为蓝灰色卵圆形巢、树枝状血管和溃疡。",
        "cause": "紫外线暴露、肤色浅、遗传（如痣样基底细胞癌综合征）",
        "treatment": "手术切除（含 Mohs 显微手术）、光动力治疗、晚期可用 Hedgehog 通路抑制剂",
        "prevention": "防晒，皮肤新生物或久不愈合的溃疡及时就诊",
    },
    "benign_keratosis": {
        "name_zh": "良性角化病（脂溢性角化等）",
        "symptoms": ["褐色或黑色扁平/疣状斑块", "表面油腻或乳头瘤样", "多无不适", "中老年多发"],
        "description": "一组良性表皮增生性病变，以脂溢性角化病（老年疣）最常见，皮肤镜下可见脑回样结构、粟丘疹样囊肿和粉刺样开口，与恶性病变的鉴别是皮肤镜检查的重点。",
        "cause": "皮肤老化、日光暴露、遗传倾向",
        "treatment": "一般无需治疗；影响美观或反复刺激者可冷冻、激光或刮除",
        "prevention": "定期皮肤自查，短期内形态颜色变化的皮损应就诊鉴别",
    },
    "dermatofibroma": {
        "name_zh": "皮肤纤维瘤",
        "symptoms": ["四肢坚硬的肤色至褐色小结节", "捏挤时中央凹陷（酒窝征）", "多无症状"],
        "description": "真皮内成纤维细胞增生形成的良性结节，好发于小腿，皮肤镜典型表现为中央白色瘢痕样区域伴周围色素网。",
        "cause": "可能与昆虫叮咬、轻微外伤后的反应性增生有关",
        "treatment": "无需治疗；诊断不确定或影响生活时手术切除",
        "prevention": "避免虫咬与皮肤外伤",
    },
    "melanoma": {
        "name_zh": "恶性黑色素瘤",
        "symptoms": ["色素痣不对称、边缘不规则", "颜色不均（黑褐蓝白混杂）", "直径 >6 mm 或近期增大", "破溃、出血、瘙痒"],
        "description": "起源于黑色素细胞的高度恶性肿瘤，是致死率最高的皮肤肿瘤。皮肤镜评估遵循 ABCDE 法则，可见不规则色素网、蓝白幕、不规则点状血管等；确诊靠切除活检，早期手术治愈率高。",
        "cause": "紫外线暴露（尤其间歇性暴晒）、多发痣、家族史、免疫抑制",
        "treatment": "早期手术扩大切除；进展期可用免疫治疗（PD-1/CTLA-4 抑制剂）与靶向治疗（BRAF/MEK）",
        "prevention": "防晒，定期皮肤镜筛查，遵循 ABCDE 法则自查色素痣",
    },
    "melanocytic_nevus": {
        "name_zh": "色素痣",
        "symptoms": ["圆形或椭圆形色素斑疹/丘疹", "颜色均匀、边界清楚", "多无症状"],
        "description": "黑色素细胞良性增生形成的最常见皮肤肿瘤，皮肤镜下色素网规则、结构对称。绝大多数为良性，但交界痣等位于摩擦部位者需关注恶变可能。",
        "cause": "遗传、日晒，黑色素细胞局灶性增生",
        "treatment": "无需治疗；反复摩擦刺激或形态改变者建议切除并病理检查",
        "prevention": "避免反复摩擦刺激与暴晒，定期自查",
    },
    "vascular_lesion": {
        "name_zh": "血管性皮肤病变",
        "symptoms": ["红色至紫红色丘疹或斑块", "压之褪色或不完全褪色", "外伤后易出血"],
        "description": "包括化脓性肉芽肿、血管瘤、血管角皮瘤等血管增生性病变，皮肤镜下以红色/紫红色无结构区（腔隙）为特征。多为良性，但化脓性肉芽肿生长快、易出血需处理。",
        "cause": "血管增生、外伤、激素变化（妊娠期化脓性肉芽肿）等",
        "treatment": "观察、冷冻、激光或手术切除；反复出血者应治疗",
        "prevention": "避免外伤，快速增大的红色皮损及时就诊",
    },
    "consolidation": {
        "name_zh": "肺实变",
        "symptoms": ["咳嗽", "咳痰", "发热", "呼吸困难", "胸痛（累及胸膜时）"],
        "description": "肺泡内气体被渗出液、血液或细胞成分取代，X 线/CT 表现为片状高密度影，内可见含气支气管征（支气管充气征）。最常见于细菌性肺炎，也见于肺出血、肺泡癌等。",
        "cause": "感染（肺炎）、肺出血、误吸、肿瘤等",
        "treatment": "针对病因：抗感染、止血或抗肿瘤治疗",
        "prevention": "接种流感/肺炎疫苗，呼吸道感染及时治疗",
    },
    "pulmonary_edema": {
        "name_zh": "肺水肿",
        "symptoms": ["呼吸困难", "端坐呼吸", "咳粉红色泡沫痰", "夜间阵发性呼吸困难"],
        "description": "肺血管内液体渗入肺间质和肺泡，X 线表现为肺门旁蝶翼状阴影、Kerley B 线、胸腔积液，常伴心影增大。是急性左心衰竭的典型影像表现。",
        "cause": "心力衰竭（心源性）、急性呼吸窘迫综合征、高原病、中毒等",
        "treatment": "坐位吸氧、利尿、扩血管，纠正基础病因（心衰治疗）",
        "prevention": "规范治疗心衰等基础病，控制液体入量",
    },
    "emphysema": {
        "name_zh": "肺气肿",
        "symptoms": ["进行性呼吸困难", "活动耐量下降", "桶状胸", "慢性咳嗽"],
        "description": "终末细支气管远端气腔持久性扩张伴肺泡壁破坏，X 线表现为肺野透亮度增加、膈肌低平、肋间隙增宽，CT 可见无壁低密度区。是 COPD 的核心病理改变之一。",
        "cause": "吸烟（最主要）、粉尘/有害气体暴露、α1-抗胰蛋白酶缺乏",
        "treatment": "戒烟、支气管扩张剂、吸入激素，晚期可肺减容或移植",
        "prevention": "戒烟，职业防护，避免呼吸道感染",
    },
    "pulmonary_fibrosis": {
        "name_zh": "肺纤维化",
        "symptoms": ["进行性呼吸困难", "干咳", "杵状指", "双下肺爆裂音（Velcro 啰音）"],
        "description": "肺间质慢性炎症后胶原沉积与瘢痕形成，X 线表现为网状/网格结节影，高分辨率 CT 典型表现为胸膜下网格影、蜂窝肺与牵拉性支气管扩张，以下肺和胸膜下分布为主。",
        "cause": "特发性（IPF）、自身免疫病、粉尘暴露（尘肺）、药物等",
        "treatment": "抗纤维化药物（吡非尼酮、尼达尼布）延缓进展，氧疗，终末期肺移植",
        "prevention": "职业粉尘防护，戒烟，结缔组织病患者定期胸部影像随访",
    },
    "pleural_thickening": {
        "name_zh": "胸膜增厚",
        "symptoms": ["多无症状", "广泛增厚时活动后气短", "患侧胸廓塌陷"],
        "description": "胸膜炎、胸腔积液吸收后或石棉暴露引起的胸膜纤维性增厚，X 线表现为胸膜缘带状高密度影、肋膈角变钝，常与胸膜钙化并存。",
        "cause": "结核性胸膜炎后遗症、脓胸、石棉暴露、胸部手术后",
        "treatment": "局限者无需治疗；广泛增厚限制呼吸时可胸膜剥脱术",
        "prevention": "积极彻底治疗胸膜炎，避免石棉暴露",
    },
    "diaphragmatic_hernia": {
        "name_zh": "膈疝",
        "symptoms": ["胸骨后烧灼感、反酸（食管裂孔疝）", "餐后胸闷气短", "肠梗阻症状（嵌顿时）"],
        "description": "腹腔脏器经膈肌缺损进入胸腔，X 线表现为心膈角区含气影或液气平面，CT 可明确疝入脏器与缺损部位。包括食管裂孔疝、Bochdalek 疝等。",
        "cause": "先天性膈肌发育缺损、腹压增高、外伤",
        "treatment": "无症状者观察；症状明显或嵌顿者手术修补",
        "prevention": "避免长期腹压增高因素，外伤后注意筛查",
    },
}

# 检查方式（模态）知识卡片
MODALITY_CARDS = {
    "CT": {
        "name_zh": "CT（计算机断层扫描）",
        "points": "X 线断层扫描重建的横断面影像，密度分辨率高，可清晰显示肺实质、腹部脏器、骨骼及病变的血供特点（增强扫描）；扫描快，是胸部、腹部和急诊影像的主力检查，但有一定电离辐射。",
    },
    "MRI": {
        "name_zh": "MRI（磁共振成像）",
        "points": "利用磁场与射频脉冲成像，无电离辐射，软组织对比度最佳，可多参数（T1/T2/弥散等）、多方向成像；是脑、脊髓、关节和盆腔病变的首选检查，缺点是扫描时间长、有幽闭恐惧与金属植入物限制。",
    },
    "X-Ray": {
        "name_zh": "X 线摄影（平片）",
        "points": "最基础的影像检查，价格低、速度快，是胸部（肺炎、气胸、心脏增大）和骨骼系统的首选初查；但为二维重叠投影，密度分辨率有限，小病灶易遗漏，必要时需 CT 进一步评估。",
    },
    "Ultrasound": {
        "name_zh": "超声成像",
        "points": "利用超声波实时成像，无辐射、便捷、可重复，是乳腺、甲状腺、腹部脏器和产科的首选筛查方法；可评估结节形态与血流（多普勒），但受气体和骨骼遮挡影响较大。",
    },
    "OCT": {
        "name_zh": "OCT（光学相干断层扫描）",
        "points": "利用低相干光干涉原理获取视网膜等组织的高分辨率断层图像（微米级），无创、快速，是黄斑疾病（新生血管、黄斑水肿、玻璃膜疣）和青光眼检查的金标准，但穿透深度有限，不能显示深层结构。",
    },
    "Fundus": {
        "name_zh": "眼底摄影",
        "points": "通过眼底相机对视网膜、视盘和视网膜血管进行彩色成像，是糖尿病视网膜病变筛查与分级、青光眼及黄斑疾病随访的基本工具；分为散瞳与免散瞳两种方式。",
    },
    "Dermoscopy": {
        "name_zh": "皮肤镜检查",
        "points": "利用偏振光或浸液消除皮肤表面反射，放大观察表皮下至真皮浅层结构的无创检查，可显示色素网、血管模式等肉眼不可见的特征，是色素性皮损（黑色素瘤、色素痣）和皮肤肿瘤良恶性鉴别的一线工具，可显著提高早期黑色素瘤检出率。",
    },
}


# ---------------------------------------------------------------- 工具函数
def load_slake_qa():
    qa = []
    for split in ("train", "validation", "test"):
        with open(os.path.join(SLAKE_DIR, split + ".json"), encoding="utf-8") as f:
            for x in json.load(f):
                x["split"] = split
                qa.append(x)
    return qa


def load_kg():
    """读取 SLAKE 知识库，返回 (英文疾病卡片, 中文疾病卡片, 器官卡片)。"""
    kg_dir = os.path.join(SLAKE_DIR, "KG", "KG")
    zh_rows = list(csv.DictReader(open(os.path.join(kg_dir, "disease.csv"), encoding="utf-8")))
    en_rows = [l.split("#") for l in open(os.path.join(kg_dir, "en_disease.csv"), encoding="utf-8").read().splitlines()[1:]]

    zh_by_dis = defaultdict(dict)
    for r in zh_rows:
        zh_by_dis[r["disease"]][r["relation"]] = r["object"]
    en_by_dis = defaultdict(dict)
    for e in en_rows:
        if len(e) >= 3:
            en_by_dis[e[0]][e[1]] = e[2]

    # 中英文疾病按出现顺序一一对应
    uzh = list(dict.fromkeys(r["disease"] for r in zh_rows))
    uen = list(dict.fromkeys(e[0] for e in en_rows if len(e) >= 3))
    en2zh = dict(zip(uen, uzh)) if len(uzh) == len(uen) else {}

    organ = defaultdict(dict)
    for r in csv.DictReader(open(os.path.join(kg_dir, "organ.csv"), encoding="utf-8")):
        organ[r["entity"]][r["property"]] = r["value"]
    return en_by_dis, zh_by_dis, en2zh, organ


def split_symptoms(s):
    return [t.strip() for t in re.split(r"[，,、]", s) if t.strip()]


def build_disease_cards(en_by_dis, zh_by_dis, en2zh):
    """合并知识库与补充卡片，生成统一疾病知识卡。"""
    cards = {}
    for en_name, card_id in DISEASE_CARD_ID.items():
        zh_name = en2zh.get(en_name)
        zh_info = zh_by_dis.get(zh_name, {}) if zh_name else {}
        if zh_info and "主要症状" in zh_info:
            cards[card_id] = {
                "card_id": card_id,
                "name_en": en_name,
                "name_zh": zh_name,
                "symptoms": split_symptoms(zh_info.get("主要症状", "")),
                "description": zh_info.get("描述", ""),
                "cause": zh_info.get("病因", ""),
                "treatment": zh_info.get("治疗方法", ""),
                "prevention": zh_info.get("预防", ""),
                "source": "SLAKE 知识库 (KG)",
            }
        elif card_id in SUPPLEMENT_CARDS:
            c = dict(SUPPLEMENT_CARDS[card_id])
            c.update({"card_id": card_id, "name_en": en_name,
                      "name_zh": c.get("name_zh", DISEASE_ZH_FALLBACK[en_name]),
                      "source": "人工整理（参考临床教材）"})
            cards[card_id] = c
        else:
            cards[card_id] = {
                "card_id": card_id, "name_en": en_name,
                "name_zh": DISEASE_ZH_FALLBACK[en_name],
                "symptoms": [], "description": "", "cause": "",
                "treatment": "", "prevention": "", "source": "待补充",
            }
    return cards


def extract_slake_images(qa):
    """从 QA 中汇总每张图片的模态/位置/器官/疾病等信息。"""
    imgs = {}
    for x in qa:
        name = x["img_name"]
        rec = imgs.setdefault(name, {
            "name": name, "location": x["location"], "modality": None,
            "weighting": None, "plane": None, "organs": set(),
            "diseases": set(), "has_disease_qa": False,
            "abnormal_flags": [], "kg_qa_zh": [],
        })
        q, a, ct = x["question"], x["answer"], x["content_type"]
        if ct == "Modality":
            if q in ("What modality is used to take this image?", "这张图片的成像方式是什么?"):
                if a in ("CT", "MRI", "X-Ray"):
                    rec["modality"] = a
            elif "加权" in q or "weighted" in q.lower():
                if a in ("T1", "T2"):
                    rec["weighting"] = a
        elif ct == "Plane" and x["answer_type"] == "OPEN":
            if a in ("横断面", "Transverse Plane", "Transverse  Plane"):
                rec["plane"] = "横断面（Axial）"
            elif a in ("冠状面", "Coronal Plane"):
                rec["plane"] = "冠状面（Coronal）"
            elif a in ("矢状面", "Sagittal Plane"):
                rec["plane"] = "矢状面（Sagittal）"
        elif ct == "Organ":
            m = re.match(r"Does the picture contain (\w+)\?", q)
            if m and a == "Yes":
                rec["organs"].add(m.group(1).lower())
            m = re.match(r"图片中包含(.+)吗\?", q)
            if m and a == "包含":
                o = m.group(1).strip()
                rec["organs"].add(ZH_ORGAN_TO_EN.get(o, o))
        elif ct == "Abnormality":
            if "What diseases" in q or "哪些疾病" in q:
                rec["has_disease_qa"] = True
                if a.strip() not in ("None", "无", ""):
                    for d in re.split(r"[,，、]", a):
                        d = DISEASE_ALIAS.get(d.strip(), d.strip())
                        if d:
                            rec["diseases"].add(d)
            elif q in ("Are there abnormalities in this image?", "图片里是否存在异常?",
                       "Does this image look abnormal?", "这张图片看起来异常吗?"):
                rec["abnormal_flags"].append(a)
        elif ct == "KG" and x["q_lang"] == "zh":
            rec["kg_qa_zh"].append({"q": q, "a": a})
    return imgs


def organ_fact(organ_zh_name, organ_kg):
    """从知识库器官词条生成一句器官知识点。"""
    info = organ_kg.get(organ_zh_name, {})
    for key in ("定义", "功能", "位置", "描述"):
        if key in info:
            return f"{organ_zh_name}：{info[key]}"
    return None


def build_slake_records(img_infos, disease_cards, organ_kg):
    records = []
    for name in sorted(img_infos, key=lambda s: int(re.sub(r"\D", "", s.split("/")[0]))):
        info = img_infos[name]
        xmlab = name.split("/")[0]
        modality = info["modality"] or "CT"
        image_id = f"slake_{xmlab}"
        rel_dir = modality.replace("-", "")
        out_rel = f"images/{rel_dir}/{image_id}.jpg"
        src = os.path.join(SLAKE_DIR, "imgs", xmlab, "source.jpg")
        dst = os.path.join(OUT, out_rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

        diseases = sorted(info["diseases"])
        cards = [disease_cards[DISEASE_CARD_ID[d]] for d in diseases if d in DISEASE_CARD_ID]

        # ---- 症状
        symptoms = []
        for c in cards:
            for s in c["symptoms"]:
                if s not in symptoms:
                    symptoms.append(s)

        # ---- 知识点
        kps = [f"【{MODALITY_ZH.get(modality, modality)}】{MODALITY_CARDS[modality]['points']}"]
        if cards:
            for c in cards:
                if c["description"]:
                    kps.append(f"【{c['name_zh']}】{c['description']}")
                if c["treatment"]:
                    kps.append(f"【{c['name_zh']}·治疗】{c['treatment']}")
        else:
            # 正常/未标注疾病：给出器官知识点
            facts = []
            for o in sorted(info["organs"]):
                zh = ORGAN_ZH.get(o, o) if o.isascii() else o
                f_ = organ_fact(zh, organ_kg)
                if f_:
                    facts.append(f_)
            kps.extend(facts[:3])
            if not info["has_disease_qa"] and not facts:
                kps.append("该图像未见明确标注的疾病征象，可作为正常对照影像学习解剖结构。")
        for kv in info["kg_qa_zh"][:2]:
            kps.append(f"【影像问答】{kv['q']} —— {kv['a']}")

        organs = []
        for o in sorted(info["organs"]):
            if o.isascii():
                organs.append({"en": o, "zh": ORGAN_ZH.get(o, o)})
            else:
                organs.append({"zh": o})

        abnormal = bool(diseases) or (
            "Yes" in info["abnormal_flags"] or "是" in info["abnormal_flags"])

        records.append({
            "image_id": image_id,
            "file": out_rel,
            "source_dataset": "SLAKE",
            "source_id": name,
            "source_url": SLAKE_URL,
            "license": "CC BY 4.0",
            "modality": modality,
            "modality_zh": MODALITY_ZH.get(modality, modality)
            + (f"（{info['weighting']} 加权）" if info["weighting"] else ""),
            "plane": info["plane"],
            "body_part": LOC_ZH.get(info["location"], info["location"]),
            "body_part_en": info["location"],
            "organs": organs,
            "is_abnormal": abnormal,
            "diseases": [
                {"en": d, "zh": disease_cards[DISEASE_CARD_ID[d]]["name_zh"],
                 "card_id": DISEASE_CARD_ID[d]}
                for d in diseases if d in DISEASE_CARD_ID
            ],
            "symptoms": symptoms if symptoms else (["无明显症状（影像未见明确异常）"] if not abnormal else ["见对应疾病典型症状"]),
            "knowledge_points": kps,
        })
    return records


def build_medmnist_records(disease_cards):
    """从 MedMNIST 的 npz 中抽样生成补充影像（乳腺超声 + 儿童胸片肺炎）。"""
    records = []
    rng = np.random.default_rng(42)

    specs = [
        # (npz 文件, split, 标签->(数量, 疾病英文名, 模态, 位置, 目录)
        ("breastmnist_64.npz", "test",
         {0: (8, "Breast Cancer"), 1: (8, "Breast Benign Lesion")},
         "Ultrasound", "乳腺", "Ultrasound"),
        ("pneumoniamnist_64.npz", "test",
         {0: (8, None), 1: (8, "Pneumonia")},
         "X-Ray", "胸部（肺）", "XRay"),
    ]
    for fname, split, label_map, modality, loc, rel_dir in specs:
        path = os.path.join(MEDMNIST_DIR, fname)
        if not os.path.exists(path):
            print(f"[warn] 缺少 {path}，跳过 MedMNIST 子集 {fname}")
            continue
        try:
            data = np.load(path)
        except Exception as e:
            print(f"[warn] {fname} 加载失败（可能下载不完整）: {e}")
            continue
        imgs = data[f"{split}_images"]
        labels = data[f"{split}_labels"].flatten()
        subset = fname.split("_")[0]
        for label, (n, disease_en) in label_map.items():
            idx = np.where(labels == label)[0]
            pick = rng.choice(idx, size=min(n, len(idx)), replace=False)
            for i, j in enumerate(sorted(pick)):
                image_id = f"medmnist_{subset}_{split}_{int(j):04d}"
                out_rel = f"images/{rel_dir}/{image_id}.png"
                dst = os.path.join(OUT, out_rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                im = Image.fromarray(imgs[j].astype(np.uint8))
                if im.mode != "L":
                    im = im.convert("L")
                im.save(dst)

                diseases = []
                symptoms = []
                kps = [f"【{MODALITY_ZH[modality]}】{MODALITY_CARDS[modality]['points']}"]
                if disease_en:
                    card = disease_cards[DISEASE_CARD_ID[disease_en]]
                    diseases = [{"en": disease_en, "zh": card["name_zh"],
                                 "card_id": card["card_id"]}]
                    symptoms = card["symptoms"]
                    if card["description"]:
                        kps.append(f"【{card['name_zh']}】{card['description']}")
                    if card["treatment"]:
                        kps.append(f"【{card['name_zh']}·治疗】{card['treatment']}")
                else:
                    symptoms = ["无明显症状（影像未见明确异常）"]
                    kps.append("该影像为正常对照胸片：双肺纹理清晰，未见实变或渗出，可用于与肺炎影像对比学习。")

                records.append({
                    "image_id": image_id,
                    "file": out_rel,
                    "source_dataset": f"MedMNIST / {subset}",
                    "source_id": f"{fname}#{split}[{int(j)}]",
                    "source_url": MEDMNIST_URL,
                    "license": "CC BY 4.0",
                    "modality": modality,
                    "modality_zh": MODALITY_ZH[modality],
                    "plane": None,
                    "body_part": loc,
                    "body_part_en": "Breast" if modality == "Ultrasound" else "Chest",
                    "organs": [{"en": "breast", "zh": "乳腺"}] if modality == "Ultrasound"
                    else [{"en": "lung", "zh": "肺"}],
                    "is_abnormal": disease_en is not None,
                    "diseases": diseases,
                    "symptoms": symptoms,
                    "knowledge_points": kps,
                    "note": "MedMNIST 标准小尺寸样本（64×64），用于模态与疾病类别补充",
                })
    return records


# ---------------------------------------------------------- 扩展数据源（第二轮扩充）
OCT_DIR = os.path.join(CACHE, "oct")
BRAINTUMOR_DIR = os.path.join(CACHE, "braintumor")
OCT_URL = "https://huggingface.co/datasets/zacharielegault/Kermany2017-OCT"
BRAINTUMOR_URL = ("https://huggingface.co/datasets/BJyotibrat/"
                  "Masoud-Nickparvar-Brain-Tumor-MRI-Dataset")

OCT_CLASSES = {0: "CNV", 1: "DME", 2: "DRUSEN", 3: None}  # None = 正常
OCT_TAG = {0: "cnv", 1: "dme", 2: "drusen", 3: "normal"}
DR_GRADES = {
    0: "0 级（未见明显视网膜病变）",
    1: "1 级（轻度非增殖性 NPDR）",
    2: "2 级（中度非增殖性 NPDR）",
    3: "3 级（重度非增殖性 NPDR）",
    4: "4 级（增殖性 PDR）",
}
FRACTURE_CLASSES = {
    0: "Buckle Rib Fracture",
    1: "Nondisplaced Rib Fracture",
    2: "Displaced Rib Fracture",
}
ORGANC_LABELS = {
    0: ("bladder", "膀胱", "盆腔"),
    1: ("femur-left", "股骨（左）", "下肢（大腿）"),
    2: ("femur-right", "股骨（右）", "下肢（大腿）"),
    3: ("heart", "心脏", "胸部（心脏）"),
    4: ("kidney-left", "肾脏（左）", "腹部（腹膜后）"),
    5: ("kidney-right", "肾脏（右）", "腹部（腹膜后）"),
    6: ("liver", "肝脏", "腹部"),
    7: ("lung-left", "肺（左）", "胸部"),
    8: ("lung-right", "肺（右）", "胸部"),
    9: ("pancreas", "胰腺", "腹部"),
    10: ("spleen", "脾脏", "腹部"),
}
ORGAN_FACT_FALLBACK = {
    "胰腺": "胰腺：位于腹膜后深处的消化与内分泌器官，分泌胰液助消化、分泌胰岛素调节血糖；CT 上呈横跨第 1-2 腰椎前方的软组织密度带。",
    "股骨": "股骨：人体最长、最粗壮的骨骼，位于大腿；CT 上骨皮质呈高密度，骨髓腔呈低密度。",
}

# 第三轮扩充：DermaMNIST 皮肤病变 / ChestMNIST 胸片多标签 / NoduleMNIST3D 肺结节
DERMA_CLASSES = {
    0: "Actinic Keratosis",
    1: "Basal Cell Carcinoma",
    2: "Benign Keratosis",
    3: "Dermatofibroma",
    4: "Melanoma",
    5: "Melanocytic Nevus",
    6: "Vascular Lesion",
}
CHEST_LABELS = {
    0: "Atelectasis", 1: "Cardiomegaly", 2: "Effusion", 3: "Infiltration",
    4: "Mass", 5: "Nodule", 6: "Pneumonia", 7: "Pneumothorax",
    8: "Consolidation", 9: "Pulmonary Edema", 10: "Emphysema",
    11: "Pulmonary Fibrosis", 12: "Pleural Thickening", 13: "Diaphragmatic Hernia",
}


def _make_record(image_id, out_rel, source_dataset, source_id, source_url,
                 modality, plane, body_part, body_part_en, organs,
                 disease_en_list, disease_cards, extra_kps=None, note=None,
                 normal_desc=None):
    """通用记录构建：由疾病卡片推导症状与知识点。"""
    cards = [disease_cards[DISEASE_CARD_ID[d]] for d in disease_en_list
             if d in DISEASE_CARD_ID]
    symptoms = []
    for c in cards:
        for s in c["symptoms"]:
            if s not in symptoms:
                symptoms.append(s)
    kps = [f"【{MODALITY_ZH[modality]}】{MODALITY_CARDS[modality]['points']}"]
    for c in cards:
        if c["description"]:
            kps.append(f"【{c['name_zh']}】{c['description']}")
        if c["treatment"]:
            kps.append(f"【{c['name_zh']}·治疗】{c['treatment']}")
    if not cards:
        symptoms = ["无明显症状（影像未见明确异常）"]
        if normal_desc:
            kps.append(normal_desc)
    if extra_kps:
        kps.extend(extra_kps)
    rec = {
        "image_id": image_id, "file": out_rel,
        "source_dataset": source_dataset, "source_id": source_id,
        "source_url": source_url, "license": "CC BY 4.0",
        "modality": modality, "modality_zh": MODALITY_ZH[modality],
        "plane": plane, "body_part": body_part, "body_part_en": body_part_en,
        "organs": organs, "is_abnormal": bool(cards),
        "diseases": [{"en": d, "zh": disease_cards[DISEASE_CARD_ID[d]]["name_zh"],
                      "card_id": DISEASE_CARD_ID[d]}
                     for d in disease_en_list if d in DISEASE_CARD_ID],
        "symptoms": symptoms, "knowledge_points": kps,
    }
    if note:
        rec["note"] = note
    return rec


def build_oct_records(disease_cards):
    """Kermany2018 视网膜 OCT：CNV / DME / 玻璃膜疣 / 正常。"""
    import io
    path = os.path.join(OCT_DIR, "test.parquet")
    if not os.path.exists(path):
        print("[warn] 缺少 OCT parquet，跳过")
        return []
    try:
        import pyarrow.parquet as pq
        t = pq.read_table(path)
    except Exception as e:
        print(f"[warn] OCT parquet 读取失败: {e}")
        return []
    imgs = t.column("image")
    labels = t.column("label").to_pylist()
    records = []
    for cls in (0, 1, 2, 3):
        idx = [i for i, l in enumerate(labels) if l == cls]
        pick = idx[:: max(1, len(idx) // 15)][:15]
        for n, i in enumerate(pick):
            row = imgs[i].as_py()
            data = row.get("bytes") or (open(row["src"], "rb").read() if row.get("src") else None)
            if not data:
                continue
            image_id = f"oct_kermany_{OCT_TAG[cls]}_{n:02d}"
            out_rel = f"images/OCT/{image_id}.jpg"
            dst = os.path.join(OUT, out_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            Image.open(io.BytesIO(data)).convert("RGB").save(dst)
            dis = [OCT_CLASSES[cls]] if OCT_CLASSES[cls] else []
            records.append(_make_record(
                image_id, out_rel, "Kermany2018 OCT", f"test[{i}]", OCT_URL,
                "OCT", None, "眼球（视网膜黄斑区）", "Eye/Retina",
                [{"zh": "视网膜"}], dis, disease_cards,
                normal_desc="该影像为正常 OCT 对照：视网膜各层结构清晰，黄斑中心凹形态完好，未见视网膜下液或异常沉积物。",
            ))
    return records


def build_braintumor_records(disease_cards):
    """脑肿瘤 MRI：胶质瘤 / 脑膜瘤 / 垂体瘤 / 无肿瘤。"""
    class_map = {"glioma": "Glioma", "meningioma": "Meningioma",
                 "pituitary": "Pituitary Tumor", "notumor": None}
    records = []
    for cls, dis in class_map.items():
        d = os.path.join(BRAINTUMOR_DIR, cls)
        if not os.path.isdir(d):
            print(f"[warn] 缺少 {d}，跳过脑肿瘤 {cls}")
            continue
        for fn in sorted(os.listdir(d)):
            if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            image_id = f"braintumor_{cls}_{os.path.splitext(fn)[0]}"
            out_rel = f"images/MRI/{image_id}.jpg"
            dst = os.path.join(OUT, out_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(d, fn), dst)
            records.append(_make_record(
                image_id, out_rel, "Brain Tumor MRI Dataset", f"Testing/{cls}/{fn}",
                BRAINTUMOR_URL, "MRI", "横断面（Axial）", "头部（脑）", "Brain",
                [{"en": "brain", "zh": "脑"}], [dis] if dis else [], disease_cards,
                extra_kps=["【影像要点】T1 增强扫描可显示肿瘤位置、强化方式与周围水肿，是脑肿瘤术前评估的核心检查。"] if dis else None,
                normal_desc="该影像为无肿瘤对照：脑实质信号未见明确占位，中线结构居中，可用于与脑肿瘤影像对比学习。",
            ))
    return records


def build_retina_records(disease_cards):
    """RetinaMNIST 眼底彩照：糖尿病视网膜病变 0-4 级。"""
    path = os.path.join(MEDMNIST_DIR, "retinamnist_64.npz")
    if not os.path.exists(path):
        print("[warn] 缺少 retinamnist_64.npz，跳过")
        return []
    try:
        data = np.load(path)
    except Exception as e:
        print(f"[warn] retinamnist 加载失败: {e}")
        return []
    imgs = data["test_images"]
    labels = data["test_labels"].flatten()
    rng = np.random.default_rng(7)
    records = []
    for g in range(5):
        idx = np.where(labels == g)[0]
        pick = rng.choice(idx, size=min(5, len(idx)), replace=False)
        for j in sorted(pick):
            image_id = f"medmnist_retinamnist_test_{int(j):04d}"
            out_rel = f"images/Fundus/{image_id}.png"
            dst = os.path.join(OUT, out_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            Image.fromarray(imgs[j].astype(np.uint8)).save(dst)
            dis = ["Diabetic Retinopathy"] if g > 0 else []
            records.append(_make_record(
                image_id, out_rel, "MedMNIST / retinamnist",
                f"retinamnist_64.npz#test[{int(j)}]", MEDMNIST_URL,
                "Fundus", None, "眼球（眼底）", "Eye/Fundus",
                [{"zh": "眼底"}], dis, disease_cards,
                extra_kps=[f"【病变分级】{DR_GRADES[g]}"],
                note="MedMNIST 标准小尺寸样本（64×64）",
                normal_desc="该眼底影像未见明确视网膜病变（0 级），可作为糖尿病视网膜病变分级的正常对照。",
            ))
    return records


def build_fracture_records(disease_cards):
    """FractureMNIST3D 肋骨 CT：三种骨折类型（取 3D 体素信息量最大的断层）。"""
    path = os.path.join(MEDMNIST_DIR, "fracturemnist3d_64.npz")
    if not os.path.exists(path):
        print("[warn] 缺少 fracturemnist3d_64.npz，跳过")
        return []
    try:
        data = np.load(path)
    except Exception as e:
        print(f"[warn] fracturemnist3d 加载失败: {e}")
        return []
    imgs = data["test_images"]
    labels = data["test_labels"].flatten()
    rng = np.random.default_rng(11)
    records = []
    for cls, dis in FRACTURE_CLASSES.items():
        idx = np.where(labels == cls)[0]
        pick = rng.choice(idx, size=min(6, len(idx)), replace=False)
        for j in sorted(pick):
            vol = imgs[j].astype(np.float32)
            s = int(vol.var(axis=(0, 1)).argmax())  # 信息量最大的断层
            sl = vol[:, :, s]
            sl = np.clip((sl - sl.min()) / max(1e-6, sl.max() - sl.min()) * 255, 0, 255)
            image_id = f"medmnist_fracturemnist3d_test_{int(j):04d}"
            out_rel = f"images/CT/{image_id}.png"
            dst = os.path.join(OUT, out_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            Image.fromarray(sl.astype(np.uint8)).save(dst)
            records.append(_make_record(
                image_id, out_rel, "MedMNIST / fracturemnist3d",
                f"fracturemnist3d_64.npz#test[{int(j)}]@slice{s}", MEDMNIST_URL,
                "CT", None, "胸壁（肋骨）", "Chest Wall/Rib",
                [{"zh": "肋骨"}], [dis], disease_cards,
                note="RibFrac 肋骨 CT 3D 体素的代表性断层（64×64）",
            ))
    return records


def build_organ_records(disease_cards, organ_kg):
    """OrganCMNIST 腹部冠状位 CT：11 类器官（解剖学习样本）。"""
    path = os.path.join(MEDMNIST_DIR, "organcmnist_64.npz")
    if not os.path.exists(path):
        print("[warn] 缺少 organcmnist_64.npz，跳过")
        return []
    try:
        data = np.load(path)
    except Exception as e:
        print(f"[warn] organcmnist 加载失败: {e}")
        return []
    imgs = data["test_images"]
    labels = data["test_labels"].flatten()
    rng = np.random.default_rng(21)
    records = []
    for cls, (en, zh, loc) in ORGANC_LABELS.items():
        idx = np.where(labels == cls)[0]
        pick = rng.choice(idx, size=min(2, len(idx)), replace=False)
        base = re.sub(r"（.+?）", "", zh)  # 去掉（左/右）后缀
        fact = organ_fact(base, organ_kg) or ORGAN_FACT_FALLBACK.get(base)
        for j in sorted(pick):
            image_id = f"medmnist_organcmnist_test_{int(j):04d}"
            out_rel = f"images/CT/{image_id}.png"
            dst = os.path.join(OUT, out_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            Image.fromarray(imgs[j].astype(np.uint8)).save(dst)
            records.append(_make_record(
                image_id, out_rel, "MedMNIST / organcmnist",
                f"organcmnist_64.npz#test[{int(j)}]", MEDMNIST_URL,
                "CT", "冠状面（Coronal）", loc, "Abdomen/Pelvis",
                [{"en": en, "zh": zh}], [], disease_cards,
                extra_kps=[fact] if fact else None,
                note="MedMNIST 标准小尺寸样本（64×64），器官标注来自 LiTS 数据集",
                normal_desc=f"该冠状位 CT 层面主要显示{zh}，未见明确病变标注，可用于腹部断层解剖学习。",
            ))
    return records


def build_derma_records(disease_cards):
    """DermaMNIST 皮肤病变皮肤镜图像（HAM10000）：7 类。"""
    path = os.path.join(MEDMNIST_DIR, "dermamnist_64.npz")
    if not os.path.exists(path):
        print("[warn] 缺少 dermamnist_64.npz，跳过")
        return []
    try:
        data = np.load(path)
    except Exception as e:
        print(f"[warn] dermamnist 加载失败: {e}")
        return []
    imgs = data["test_images"]
    labels = data["test_labels"].flatten()
    rng = np.random.default_rng(31)
    records = []
    for cls, dis in DERMA_CLASSES.items():
        idx = np.where(labels == cls)[0]
        pick = rng.choice(idx, size=min(5, len(idx)), replace=False)
        for j in sorted(pick):
            image_id = f"medmnist_dermamnist_test_{int(j):04d}"
            out_rel = f"images/Dermoscopy/{image_id}.png"
            dst = os.path.join(OUT, out_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            Image.fromarray(imgs[j].astype(np.uint8)).save(dst)
            records.append(_make_record(
                image_id, out_rel, "MedMNIST / dermamnist",
                f"dermamnist_64.npz#test[{int(j)}]", MEDMNIST_URL,
                "Dermoscopy", None, "皮肤", "Skin",
                [{"en": "skin", "zh": "皮肤"}], [dis], disease_cards,
                note="MedMNIST 标准小尺寸样本（64×64），原始来源 HAM10000 皮肤镜数据集",
            ))
    return records


def build_chest_records(disease_cards):
    """ChestMNIST 胸片多标签（NIH CXR14 子集）：14 类疾病，每类抽单标签样本。"""
    path = os.path.join(MEDMNIST_DIR, "chestmnist_64.npz")
    if not os.path.exists(path):
        print("[warn] 缺少 chestmnist_64.npz，跳过")
        return []
    try:
        data = np.load(path)
    except Exception as e:
        print(f"[warn] chestmnist 加载失败: {e}")
        return []
    imgs = data["test_images"]
    labels = data["test_labels"]  # 多标签 (N, 14)
    rng = np.random.default_rng(41)
    records = []
    for cls, dis in CHEST_LABELS.items():
        # 只取该标签为唯一阳性的样本，保证疾病标注明确
        mask = (labels[:, cls] == 1) & (labels.sum(axis=1) == 1)
        idx = np.where(mask)[0]
        if len(idx) == 0:
            mask = labels[:, cls] == 1
            idx = np.where(mask)[0]
        pick = rng.choice(idx, size=min(4, len(idx)), replace=False)
        for j in sorted(pick):
            image_id = f"medmnist_chestmnist_test_{int(j):05d}"
            out_rel = f"images/XRay/{image_id}.png"
            dst = os.path.join(OUT, out_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            Image.fromarray(imgs[j].astype(np.uint8)).save(dst)
            records.append(_make_record(
                image_id, out_rel, "MedMNIST / chestmnist",
                f"chestmnist_64.npz#test[{int(j)}]", MEDMNIST_URL,
                "X-Ray", None, "胸部（肺）", "Chest",
                [{"en": "lung", "zh": "肺"}], [dis], disease_cards,
                note="MedMNIST 标准小尺寸样本（64×64），多标签来自 NIH ChestX-ray14",
            ))
    return records


def build_nodule3d_records(disease_cards):
    """NoduleMNIST3D 肺结节 CT（LUNA16 子集）：取信息量最大的断层。"""
    path = os.path.join(MEDMNIST_DIR, "nodulemnist3d_64.npz")
    if not os.path.exists(path):
        print("[warn] 缺少 nodulemnist3d_64.npz，跳过")
        return []
    try:
        data = np.load(path)
    except Exception as e:
        print(f"[warn] nodulemnist3d 加载失败: {e}")
        return []
    imgs = data["test_images"]
    labels = data["test_labels"].flatten()
    rng = np.random.default_rng(51)
    records = []
    # 0 = 正常（无结节），1 = 肺结节
    for cls, dis in [(0, None), (1, "Pulmonary Nodule")]:
        idx = np.where(labels == cls)[0]
        pick = rng.choice(idx, size=min(8, len(idx)), replace=False)
        for j in sorted(pick):
            vol = imgs[j].astype(np.float32)
            s = int(vol.var(axis=(0, 1)).argmax())
            sl = vol[:, :, s]
            sl = np.clip((sl - sl.min()) / max(1e-6, sl.max() - sl.min()) * 255, 0, 255)
            image_id = f"medmnist_nodulemnist3d_test_{int(j):04d}"
            out_rel = f"images/CT/{image_id}.png"
            dst = os.path.join(OUT, out_rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            Image.fromarray(sl.astype(np.uint8)).save(dst)
            records.append(_make_record(
                image_id, out_rel, "MedMNIST / nodulemnist3d",
                f"nodulemnist3d_64.npz#test[{int(j)}]@slice{s}", MEDMNIST_URL,
                "CT", None, "胸部（肺）", "Chest",
                [{"en": "lung", "zh": "肺"}], [dis] if dis else [], disease_cards,
                note="LUNA16 肺结节 CT 3D 体素的代表性断层（64×64）",
                normal_desc="该 CT 断层未见明确肺结节标注，可作为肺结节筛查的正常对照。",
            ))
    return records


def write_metadata(records, disease_cards, organ_kg):
    meta_dir = os.path.join(OUT, "metadata")
    os.makedirs(meta_dir, exist_ok=True)

    stats = {
        "total_images": len(records),
        "by_modality": dict(Counter(r["modality"] for r in records)),
        "by_body_part": dict(Counter(r["body_part"] for r in records)),
        "abnormal": sum(1 for r in records if r["is_abnormal"]),
        "by_disease": dict(Counter(d["zh"] for r in records for d in r["diseases"])),
    }
    library = {
        "name": "医学影像学图像库",
        "description": "每张影像均标注：相关症状、解剖位置、知识点。数据来自开源项目 SLAKE、MedMNIST、Kermany2018 OCT、Brain Tumor MRI Dataset（均为 CC BY 4.0 许可）。仅供学习研究，不用于临床诊断。",
        "sources": [
            {"project": "SLAKE (Bo-Li-Lab/SLAKE)", "url": SLAKE_URL,
             "github": "https://github.com/Bo-Li-Lab/SLAKE", "license": "CC BY 4.0",
             "content": "642 张 CT/MRI/X-Ray 影像 + 中英双语问答 + 医学知识库"},
            {"project": "MedMNIST (MedMNIST/MedMNIST)", "url": MEDMNIST_URL,
             "github": MEDMNIST_URL, "license": "CC BY 4.0",
             "content": "标准化生物医学影像分类数据集（本库采用 BreastMNIST 乳腺超声、PneumoniaMNIST 胸片肺炎、RetinaMNIST 眼底、FractureMNIST3D 肋骨骨折、OrganCMNIST 腹部器官、DermaMNIST 皮肤病变、ChestMNIST 胸片 14 病、NoduleMNIST3D 肺结节）"},
            {"project": "Kermany2018 OCT (zacharielegault/Kermany2017-OCT)", "url": OCT_URL,
             "github": OCT_URL, "license": "CC BY 4.0",
             "content": "视网膜 OCT 分类数据集（CNV / DME / 玻璃膜疣 / 正常），原始来源 Kermany et al. Cell 2018"},
            {"project": "Brain Tumor MRI Dataset (BJyotibrat)", "url": BRAINTUMOR_URL,
             "github": BRAINTUMOR_URL, "license": "CC BY 4.0",
             "content": "脑肿瘤 MRI 四分类（胶质瘤 / 脑膜瘤 / 垂体瘤 / 无肿瘤），原始来源 Kaggle (Masoud Nickparvar)"},
        ],
        "stats": stats,
        "images": records,
    }
    with open(os.path.join(meta_dir, "library.json"), "w", encoding="utf-8") as f:
        json.dump(library, f, ensure_ascii=False, indent=1)

    kb = {
        "diseases": disease_cards,
        "modalities": MODALITY_CARDS,
        "organs": {k: dict(v) for k, v in list(organ_kg.items())[:120]},
    }
    with open(os.path.join(meta_dir, "knowledge_base.json"), "w", encoding="utf-8") as f:
        json.dump(kb, f, ensure_ascii=False, indent=1)

    with open(os.path.join(meta_dir, "library.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["image_id", "file", "modality", "modality_zh", "plane", "body_part",
                    "organs", "is_abnormal", "diseases_zh", "symptoms", "knowledge_points",
                    "source_dataset", "license"])
        for r in records:
            w.writerow([
                r["image_id"], r["file"], r["modality"], r["modality_zh"], r["plane"] or "",
                r["body_part"],
                "、".join(o.get("zh", o.get("en", "")) for o in r["organs"]),
                "异常" if r["is_abnormal"] else "正常/对照",
                "、".join(d["zh"] for d in r["diseases"]) or "无",
                "、".join(r["symptoms"]),
                " | ".join(r["knowledge_points"]),
                r["source_dataset"], r["license"],
            ])
    return library


def main():
    os.makedirs(OUT, exist_ok=True)
    qa = load_slake_qa()
    en_by_dis, zh_by_dis, en2zh, organ_kg = load_kg()
    disease_cards = build_disease_cards(en_by_dis, zh_by_dis, en2zh)

    img_infos = extract_slake_images(qa)
    print(f"SLAKE 图像: {len(img_infos)} 张")
    slake_records = build_slake_records(img_infos, disease_cards, organ_kg)
    medmnist_records = build_medmnist_records(disease_cards)
    print(f"MedMNIST 基础抽样: {len(medmnist_records)} 张")

    ext_records = []
    ext_records += build_oct_records(disease_cards)
    ext_records += build_braintumor_records(disease_cards)
    ext_records += build_retina_records(disease_cards)
    ext_records += build_fracture_records(disease_cards)
    ext_records += build_organ_records(disease_cards, organ_kg)
    ext_records += build_derma_records(disease_cards)
    ext_records += build_chest_records(disease_cards)
    ext_records += build_nodule3d_records(disease_cards)
    print(f"扩展数据源抽样: {len(ext_records)} 张")

    records = slake_records + medmnist_records + ext_records
    library = write_metadata(records, disease_cards, organ_kg)
    print(json.dumps(library["stats"], ensure_ascii=False, indent=1))
    print("DONE")


if __name__ == "__main__":
    main()
