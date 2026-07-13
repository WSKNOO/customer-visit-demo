"""
Keyword Generator — 根据客户名称自动生成多维搜索关键词。

依据需求文档第8节的关键词模板，覆盖企业画像、数字化、AI、云、安全、
招投标、合作动态、年报等多个维度。
"""

from typing import Dict, List


# ── 搜索维度定义 ────────────────────────────────────────────────────────────

SEARCH_DIMENSIONS: List[Dict] = [
    {
        "name": "企业画像",
        "priority": "high",
        "templates": [
            "{company} 官网",
            "{company} 简介 主营业务",
            "{company} 企业性质 所属行业",
            "{company} 上级单位 集团",
            "{company} 组织架构 领导班子",
        ],
    },
    {
        "name": "数字化转型",
        "priority": "high",
        "templates": [
            "{company} 数字化转型",
            "{company} 信息化 数字化",
            "{company} 智慧化 智能化",
            "{company} 数据治理 数据中台",
        ],
    },
    {
        "name": "人工智能",
        "priority": "high",
        "templates": [
            "{company} 人工智能",
            "{company} 大模型 AI",
            "{company} 机器学习 深度学习",
            "{company} 智能算法 计算机视觉",
        ],
    },
    {
        "name": "云计算与算力",
        "priority": "high",
        "templates": [
            "{company} 云平台 云计算",
            "{company} 算力 数据中心",
            "{company} 私有云 混合云",
            "{company} 信创 国产化替代",
        ],
    },
    {
        "name": "网络安全",
        "priority": "medium",
        "templates": [
            "{company} 网络安全",
            "{company} 数据安全 信息安全",
            "{company} 等级保护 合规",
            "{company} 密码应用 安全评估",
        ],
    },
    {
        "name": "5G与物联网",
        "priority": "medium",
        "templates": [
            "{company} 5G",
            "{company} 物联网 IoT",
            "{company} 工业互联网",
            "{company} 智慧园区 智慧工厂",
        ],
    },
    {
        "name": "招投标与采购",
        "priority": "high",
        "templates": [
            "{company} 招标 采购",
            "{company} 中标 项目建设",
            "{company} 信息化项目 集成项目",
            "{company} 软件采购 系统建设",
        ],
    },
    {
        "name": "战略合作",
        "priority": "high",
        "templates": [
            "{company} 战略合作 签约",
            "{company} 合作伙伴 生态",
            "{company} 会议 论坛 峰会",
            "{company} 领导讲话 调研",
        ],
    },
    {
        "name": "年度报告",
        "priority": "medium",
        "templates": [
            "{company} 年报 财报",
            "{company} 社会责任报告",
            "{company} 白皮书 研究报告",
            "{company} 发展规划 十四五",
        ],
    },
    {
        "name": "新闻动态",
        "priority": "high",
        "templates": [
            "{company} 最新新闻",
            "{company} 重大公告",
            "{company} 项目签约 合作",
            "{company} 表彰 荣誉 资质",
        ],
    },
    {
        "name": "行业定位",
        "priority": "medium",
        "templates": [
            "{company} 行业排名 市场份额",
            "{company} 核心竞争力 优势",
            "{company} 改革 重组 上市",
            "{company} 子公司 分支机构",
        ],
    },
    {
        "name": "信创与国产化",
        "priority": "high",
        "templates": [
            "{company} 信创 信创替代",
            "{company} 国产化 自主可控",
            "{company} 操作系统 数据库替代",
            "{company} 芯片 服务器 国产",
        ],
    },
]


def generate_keywords(company_name: str, focus_areas: List[str] = None) -> List[Dict]:
    """
    根据客户名称生成多维度搜索关键词。

    Args:
        company_name: 客户企业名称。
        focus_areas: 指定的关注方向（如 ['AI', '人工智能', '云', '安全']），为空则全维度。
                     支持中英文关键词自动匹配。

    Returns:
        关键词列表，每个元素为 {'dimension': str, 'priority': str, 'keywords': List[str]}。
    """
    # 英文→中文关注方向映射表
    AREA_ALIASES = {
        "ai": "人工智能",
        "人工智能": "人工智能",
        "artificial intelligence": "人工智能",
        "cloud": "云计算与算力",
        "云": "云计算与算力",
        "云计算": "云计算与算力",
        "security": "网络安全",
        "安全": "网络安全",
        "网络安全": "网络安全",
        "data": "大数据",
        "大数据": "大数据",
        "5g": "5G与物联网",
        "iot": "5G与物联网",
        "物联网": "5G与物联网",
        "big data": "大数据",
        "digital": "数字化转型",
        "数字化": "数字化转型",
        "数字化转型": "数字化转型",
        "信创": "信创与国产化",
        "国产化": "信创与国产化",
        "it": "数字化转型",
        "信息化": "数字化转型",
    }

    results = []

    for dim in SEARCH_DIMENSIONS:
        # 如果有指定关注方向，只匹配相关维度
        if focus_areas:
            dim_name = dim["name"].lower()
            matched = False
            for area in focus_areas:
                area_lower = area.strip().lower()
                # 精确匹配维度名
                if area_lower == dim_name:
                    matched = True
                    break
                # 别名映射
                mapped = AREA_ALIASES.get(area_lower, "")
                if mapped and mapped.lower() == dim_name:
                    matched = True
                    break
                # 维度名包含关注词
                if area_lower in dim_name:
                    matched = True
                    break
            if not matched:
                continue

        keywords = [t.format(company=company_name) for t in dim["templates"]]
        results.append({
            "dimension": dim["name"],
            "priority": dim["priority"],
            "keywords": keywords,
        })

    # 如果没有匹配到任何维度，返回所有维度
    if not results:
        for dim in SEARCH_DIMENSIONS:
            keywords = [t.format(company=company_name) for t in dim["templates"]]
            results.append({
                "dimension": dim["name"],
                "priority": dim["priority"],
                "keywords": keywords,
            })

    return results


def generate_flat_keywords(company_name: str, focus_areas: List[str] = None) -> List[str]:
    """生成扁平化的关键词列表（不加维度分组）。"""
    keywords = []
    for dim in generate_keywords(company_name, focus_areas):
        keywords.extend(dim["keywords"])
    return keywords


def get_dimension_names() -> List[str]:
    """返回所有维度名称列表。"""
    return [d["name"] for d in SEARCH_DIMENSIONS]