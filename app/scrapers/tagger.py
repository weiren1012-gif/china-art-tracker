"""中国流失海外石窟寺文物关键词识别。

两档匹配策略:
- 强特征词(title 或 description 命中即打标):佛像、石窟名、buddha、stone sculpture 等
- 弱特征词(仅 title 命中才打标):造像、釋迦、壁畫等,防止描述文本中的
  碑帖"造像记"、山水画"敦煌背景介绍"等上下文造成误标
"""

STRONG_KEYWORDS = [
    # 中文
    "佛像", "佛頭", "佛头", "坐佛", "立佛", "石佛", "造像碑", "碑像",
    "石窟", "洞窟", "佛窟", "石雕佛", "石窟寺",
    "敦煌", "莫高窟", "雲岡", "云冈", "龍門石窟", "龙门石窟",
    "麥積山", "麦积山", "炳靈寺", "炳灵寺", "天龍山", "天龙山",
    "響堂山", "响堂山", "克孜爾", "克孜尔", "庫木吐喇", "库木吐喇",
    "榆林窟", "藏經洞", "藏经洞", "敦煌遺書", "敦煌遗书",
    "壁畫", "壁画", "飛天", "飞天", "伎樂天", "伎乐天", "供養人", "供养人",
    "寫經", "写经", "經卷", "经卷", "妙法蓮華經", "妙法莲华经",
    "維摩詰", "维摩诘", "法華經", "法华经", "金剛經", "金刚经", "佛經", "佛经",
    "藥師佛", "药师佛",
    # 英文
    "buddha", "bodhisattva", "sakyamuni", "shakyamuni", "maitreya",
    "amitabha", "bhaisajyaguru", "kstitigarbha", "lokesvara",
    "stone sculpture", "stone carving", "stone head", "stone torso",
    "stela", "stele", "stupa", "apsara", "grotto", "cave temple",
    "monk statue", "buddhist figure", "buddha head", "buddha figure",
    "seated buddha", "standing buddha", "gilt bronze buddha",
    "fresco", "dunhuang", "mogao", "yungang", "longmen", "tianlongshan",
    "maijishan", "kizil", "cave-temple",
]

WEAK_KEYWORDS = [
    # 仅在标题中命中才打标
    "造像", "釋迦", "释迦", "如來", "如来", "彌勒", "弥勒",
    "阿彌陀", "阿弥陀", "地藏", "觀音像", "观音像", "羅漢像", "罗汉像",
    "天王像", "佛龕", "佛龛", "石雕",
    "明中期",  # 保留?不,明中期太泛,不加
]

TAG_GROTTO = "grotto"


def _text(lot):
    return " ".join(
        str(lot.get(k) or "") for k in ("title", "description", "category", "sale_title")
    ).lower()


def match_lot(lot):
    """判断拍品是否属于石窟寺文物。"""
    text = _text(lot)
    title = " ".join(str(lot.get(k) or "") for k in ("title", "category", "sale_title")).lower()
    for kw in STRONG_KEYWORDS:
        if kw.lower() in text:
            return True
    for kw in WEAK_KEYWORDS:
        if kw.lower() in title:
            return True
    return False


def tag_lot(lot):
    """对单个拍品打标,返回 tags 字符串。"""
    tags = []
    if match_lot(lot):
        tags.append(TAG_GROTTO)
    lot["tags"] = ",".join(tags)
    return lot


def tag_lots(lots):
    for lot in lots:
        tag_lot(lot)
    return lots
