"""
Product Catalog — 静态产品能力表。

模拟内部产品能力库，用于匹配客户需求与可推荐产品方案。
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class ProductCapability:
    """产品能力条目。"""
    id: str
    name: str
    category: str
    description: str
    keywords: List[str]  # 匹配关键词
    scenarios: List[str]  # 适用场景
    typical_clients: List[str] = field(default_factory=list)


# ── 产品能力表（Demo 用静态数据）────────────────────────────────────────────

PRODUCT_CATALOG = [
    ProductCapability(
        id="AI-001",
        name="企业AI大模型平台",
        category="人工智能",
        description="基于主流大模型（GPT/LLaMA/文心/通义等）的企业私有化部署平台，支持知识库问答、文档生成、智能客服、代码辅助等场景。",
        keywords=["大模型", "AI", "人工智能", "LLM", "知识库", "智能问答", "AIGC", "生成式AI"],
        scenarios=["智能客服", "知识管理", "文档自动化", "研发提效", "智能决策"],
    ),
    ProductCapability(
        id="AI-002",
        name="智能文档理解与处理平台",
        category="人工智能",
        description="基于OCR+NLP+大模型的文档智能处理系统，支持合同审查、发票识别、报表分析、档案数字化。",
        keywords=["文档理解", "OCR", "合同审查", "文档处理", "智能识别", "档案数字化"],
        scenarios=["合同审查", "财务票据处理", "档案管理", "报表分析"],
    ),
    ProductCapability(
        id="AI-003",
        name="AI中台与模型管理平台",
        category="人工智能",
        description="统一管理AI模型的全生命周期，包括训练、评估、部署、监控，支持MLOps最佳实践。",
        keywords=["AI中台", "MLOps", "模型管理", "模型部署", "算法平台"],
        scenarios=["模型统一管理", "AI资产沉淀", "模型合规"],
    ),
    ProductCapability(
        id="DATA-001",
        name="数据中台解决方案",
        category="大数据",
        description="企业级数据中台，包括数据采集、数据治理、数据开发、数据服务、数据可视化全链路能力。",
        keywords=["数据中台", "数据治理", "数据湖", "数据仓库", "ETL", "数据资产", "主数据"],
        scenarios=["数据整合", "数据治理", "数据分析", "数据服务", "BI分析"],
    ),
    ProductCapability(
        id="DATA-002",
        name="大数据分析平台",
        category="大数据",
        description="面向海量数据的交互式分析平台，支持SQL分析、实时计算、数据可视化、自助分析。",
        keywords=["大数据分析", "BI", "数据分析", "实时计算", "可视化", "Flink", "Spark"],
        scenarios=["经营分析", "实时监控", "报表系统", "数据大屏"],
    ),
    ProductCapability(
        id="DATA-003",
        name="数据治理与数据质量平台",
        category="大数据",
        description="涵盖元数据管理、数据标准、数据质量、数据安全、数据生命周期的全面治理平台。",
        keywords=["数据治理", "元数据", "数据标准", "数据质量", "数据安全", "数据血缘"],
        scenarios=["数据治理体系建设", "数据质量提升", "数据合规"],
    ),
    ProductCapability(
        id="CLOUD-001",
        name="私有云/混合云解决方案",
        category="云计算",
        description="基于OpenStack/Kubernetes的企业私有云和混合云解决方案，支持统一资源管理、弹性伸缩、多租户。",
        keywords=["私有云", "混合云", "云平台", "虚拟化", "容器云", "Kubernetes", "OpenStack"],
        scenarios=["IT基础设施云化", "应用容器化", "资源统一管理"],
    ),
    ProductCapability(
        id="CLOUD-002",
        name="信创云解决方案",
        category="云计算",
        description="全栈信创兼容的云平台，支持国产CPU（鲲鹏/飞腾/海光）和国产操作系统，通过信创适配验证。",
        keywords=["信创云", "国产化", "自主可控", "信创适配", "鲲鹏", "飞腾", "麒麟"],
        scenarios=["信创替代", "国产化迁移", "信创合规"],
    ),
    ProductCapability(
        id="SEC-001",
        name="数据安全与隐私保护平台",
        category="网络安全",
        description="覆盖数据分类分级、数据脱敏、数据水印、数据溯源、隐私计算的全面数据安全方案。",
        keywords=["数据安全", "隐私计算", "数据脱敏", "分类分级", "数据水印", "隐私保护"],
        scenarios=["数据安全合规", "隐私保护", "数据出境管理"],
    ),
    ProductCapability(
        id="SEC-002",
        name="零信任安全架构",
        category="网络安全",
        description="基于零信任理念的新一代网络安全架构，包括身份认证、权限管理、微隔离、持续验证。",
        keywords=["零信任", "身份认证", "IAM", "微隔离", "SDP", "网络安全"],
        scenarios=["远程办公安全", "内网安全", "多云安全"],
    ),
    ProductCapability(
        id="IOT-001",
        name="物联网平台",
        category="物联网",
        description="设备接入、数据采集、远程监控、规则引擎、边缘计算一体化的物联网平台。",
        keywords=["物联网", "IoT", "设备接入", "边缘计算", "物模型", "设备管理"],
        scenarios=["工业物联网", "智慧园区", "设备监控"],
    ),
    ProductCapability(
        id="IOT-002",
        name="智慧园区解决方案",
        category="物联网",
        description="基于IoT+AI的智慧园区综合管理平台，涵盖安防、能耗、停车、访客、物业等场景。",
        keywords=["智慧园区", "智慧楼宇", "园区管理", "能耗管理", "智慧安防"],
        scenarios=["园区运营", "节能减排", "安防管理"],
    ),
    ProductCapability(
        id="DIGITAL-001",
        name="企业数字化转型咨询",
        category="数字化咨询",
        description="从战略到落地的数字化转型全流程咨询服务，包括现状评估、蓝图规划、路径设计、实施辅导。",
        keywords=["数字化转型", "数字化咨询", "信息化规划", "顶层设计", "数字战略"],
        scenarios=["战略规划", "转型评估", "数字化路径"],
    ),
    ProductCapability(
        id="DIGITAL-002",
        name="协同办公与数字化工作平台",
        category="数字化应用",
        description="企业级协同办公平台，融合即时通讯、文档协作、流程审批、知识管理、项目管理。",
        keywords=["协同办公", "OA", "办公自动化", "流程审批", "知识管理", "企业门户"],
        scenarios=["办公提效", "流程优化", "协同管理"],
    ),
    ProductCapability(
        id="DIGITAL-003",
        name="低代码应用开发平台",
        category="数字化应用",
        description="可视化低代码开发平台，支持快速搭建业务应用、表单、流程、报表，降低开发门槛。",
        keywords=["低代码", "无代码", "快速开发", "应用搭建", "表单流程"],
        scenarios=["快速应用开发", "业务数字化", "遗留系统改造"],
    ),
    ProductCapability(
        id="AI-004",
        name="计算机视觉与视频分析平台",
        category="人工智能",
        description="基于深度学习的图像/视频分析平台，支持人脸识别、行为分析、OCR、缺陷检测等。",
        keywords=["计算机视觉", "视频分析", "人脸识别", "图像识别", "OCR", "缺陷检测"],
        scenarios=["安防监控", "质量检测", "身份核验", "视频结构化"],
    ),
]


def get_product_by_id(product_id: str) -> ProductCapability:
    """根据ID查找产品。"""
    for p in PRODUCT_CATALOG:
        if p.id == product_id:
            return p
    raise KeyError(f"Product not found: {product_id}")


def search_products(keywords: List[str]) -> List[ProductCapability]:
    """根据关键词匹配产品能力。"""
    matched = []
    for product in PRODUCT_CATALOG:
        score = 0
        for kw in keywords:
            kw_lower = kw.lower()
            for pk in product.keywords:
                if kw_lower in pk.lower() or pk.lower() in kw_lower:
                    score += 1
            for scene in product.scenarios:
                if kw_lower in scene.lower():
                    score += 1
        if score > 0:
            matched.append((product, score))
    matched.sort(key=lambda x: x[1], reverse=True)
    return [m[0] for m in matched]


def get_all_categories() -> List[str]:
    """返回所有产品类别。"""
    cats = set()
    for p in PRODUCT_CATALOG:
        cats.add(p.category)
    return sorted(cats)


def format_catalog_text() -> str:
    """将产品目录格式化为文本，方便放入Prompt。"""
    lines = []
    for p in PRODUCT_CATALOG:
        lines.append(f"【{p.id}】{p.name}（{p.category}）")
        lines.append(f"  简介：{p.description}")
        lines.append(f"  关键词：{'、'.join(p.keywords)}")
        lines.append(f"  场景：{'、'.join(p.scenarios)}")
        lines.append("")
    return "\n".join(lines)