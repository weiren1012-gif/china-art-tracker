# 中国文物拍卖追踪系统

实时追踪**世界主要国家和地区拍卖行**中关于中国文物拍品的公开信息,提供 Web 界面浏览、搜索、筛选,并通过 Cloudflare 隧道让外网任何人均可访问。内置**流失海外石窟寺文物专项板块**,自动识别佛像、造像、壁画、经卷等石窟寺相关文物。

## 已接入拍卖行(11 家)

| 拍卖行 | 地区 | 数据源 |
|---|---|---|
| Christie's 佳士得 | 全球(英/美/港/法) | apim.christies.com.cn 公开 API |
| Sotheby's 苏富比 | 全球(英/美/港/法) | Algolia 搜索 API |
| Bonhams 邦瀚斯 | 全球(英/美/港) | Typesense API |
| Dreweatts | 英国 | SSR HTML 解析 |
| Woolley & Wallis | 英国 | umbraco JSON API |
| Artcurial | 法国 | ace REST API(Art d'Asie 专场) |
| Tokyo Chuo 东京中央 | 日本 | tcabid.com Rails API(中国文物量最大) |
| Seoul Auction | 韩国 | /api/auction/*(古美术分类) |
| K Auction | 韩国 | k-auction.com API |
| Poly 保利香港 | 香港 | polyauctionhk.com 公开 API |
| Guardian 嘉德香港 | 香港 | cguardian.com.hk 签名 API |

> 注:Heritage Auctions(美)因全站 DataDome 反爬无法用脚本访问,暂未接入;Phillips(富艺斯)中国文物极少且反爬严格,暂未接入。

## 功能

- **自动抓取**:每 6 小时定时轮询(`POLL_INTERVAL_HOURS` 可调),也可手动触发
- **石窟寺文物板块**:两级关键词自动识别(强词标题+描述、弱词仅标题,共 100+ 词),独立板块展示流失海外的佛像/造像/壁画/经卷
- **新增记录列表**:每次扫描发现的新拍品按首次发现时间记录,专属页面展示
- **完整拍品信息**:名称、描述、估价、成交价、图片、拍卖会、官网链接
- **Web 界面**:板块切换、关键字搜索、按来源/状态/价格排序筛选、详情弹窗、统计面板、抓取日志
- **扫码访问**:网页右上角「二维码」按钮,弹窗展示当前外网地址二维码

## 启动

```bash
./start.sh          # 启动 Web + 隧道
./watchdog.sh &     # 看门狗:服务/隧道挂了自动重启
```

- 本地:`http://localhost:8001`
- 外网地址:`cat data/tunnel.url`(或 grep data/tunnel.log)
  (快速隧道域名每次重启会变,二维码在网页右上角可随时查看)

## 常用操作

```bash
# 手动抓取全部来源(后台)
curl -X POST http://localhost:8001/api/fetch

# 抓取单个来源
curl -X POST http://localhost:8001/api/fetch?source=guardian

# 石窟寺文物列表
curl "http://localhost:8001/api/lots?tag=grotto&sort=price_high"

# 最近新增记录
curl "http://localhost:8001/api/lots/new?limit=100"

# 统计(含石窟寺文物数)
curl http://localhost:8001/api/stats
```

## 配置(app/config.py 或环境变量)

| 变量 | 默认 | 说明 |
|---|---|---|
| `POLL_INTERVAL_HOURS` | 6 | 定时轮询间隔(小时) |
| `RESULTS_LOOKBACK_DAYS` | 30 | 每次轮询追溯最近 N 天成交结果 |
| `REQUEST_DELAY` | 1.0 | 请求间隔(秒) |
| `MAX_PAGES` | 40 | 单次轮询每来源最多抓取页数 |

## 项目结构

```
app/
  main.py          # FastAPI 入口 + API
  scheduler.py     # APScheduler 定时任务
  database.py      # SQLite 存储(拍品去重、新增记录)
  tunnel.py        # 隧道地址 + 二维码
  scrapers/
    base.py        # 公共请求/限速/重试
    tagger.py      # 石窟寺文物关键词识别(121 词)
    christies.py sothebys.py bonhams.py
    dreweatts.py woolley.py artcurial.py
    tokyochuo.py seoul.py kauction.py
    poly.py guardian.py
  static/          # 前端(板块 tab / 二维码 / 详情弹窗)
data/              # SQLite 数据库与日志
```

## 注意事项

- 数据均来自各拍卖行官网公开接口,请控制请求频率(默认已限速)
- 石窟寺文物识别基于标题/描述关键词匹配,个别拍品可能误标或漏标
- Cloudflare 快速隧道域名每次重启变化;如需固定地址请配置命名隧道
