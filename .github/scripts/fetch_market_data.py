#!/usr/bin/env python3
"""
获取全球市场数据

收集美股、港股、债市、汇率和主要市场新闻
"""

import os
import sys
import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta


def fetch_stock_data(symbol, api_key):
    """获取股票数据（使用 Alpha Vantage 或备用方案）"""
    # 这里使用 Yahoo Finance API 作为免费方案
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        result = data.get('chart', {}).get('result', [{}])[0]
        meta = result.get('meta', {})
        timestamps = result.get('timestamp', [])
        closes = result.get('indicators', {}).get('quote', [{}])[0].get('close', [])
        
        if not timestamps or not closes:
            return None
        
        current_price = closes[-1]
        prev_price = closes[-2] if len(closes) > 1 else current_price
        change = current_price - prev_price
        change_pct = (change / prev_price * 100) if prev_price else 0
        
        return {
            'symbol': symbol,
            'name': meta.get('shortName', symbol),
            'price': round(current_price, 2),
            'change': round(change, 2),
            'change_pct': round(change_pct, 2),
            'currency': meta.get('currency', 'USD')
        }
    except Exception as e:
        print(f"⚠️  获取 {symbol} 失败: {e}")
        return None


def fetch_us_stocks():
    """获取美股主要指数"""
    print("📈 获取美股数据...")
    
    symbols = {
        '^GSPC': '标普 500',
        '^DJI': '道琼斯',
        '^IXIC': '纳斯达克',
        'AAPL': '苹果',
        'MSFT': '微软',
        'NVDA': '英伟达',
        'TSLA': '特斯拉',
        'BABA': '阿里巴巴(美)'
    }
    
    results = []
    for symbol, name in symbols.items():
        data = fetch_stock_data(symbol, None)
        if data:
            data['name'] = name
            results.append(data)
    
    print(f"✅ 获取 {len(results)} 支美股数据")
    return results


def fetch_hk_stocks():
    """获取港股主要指数"""
    print("📈 获取港股数据...")
    
    # Yahoo Finance 港股代码格式
    symbols = {
        '^HSI': '恒生指数',
        '^HSTECH': '恒生科技',
        '0700.HK': '腾讯控股',
        '3690.HK': '美团',
        '9988.HK': '阿里巴巴',
        '1810.HK': '小米集团',
        '2318.HK': '中国平安'
    }
    
    results = []
    for symbol, name in symbols.items():
        data = fetch_stock_data(symbol, None)
        if data:
            data['name'] = name
            results.append(data)
    
    print(f"✅ 获取 {len(results)} 支港股数据")
    return results


def fetch_cn_stocks():
    """获取 A 股主要指数"""
    print("📈 获取 A 股数据...")
    
    symbols = {
        '000001.SS': '上证指数',
        '399001.SZ': '深证成指',
        '399006.SZ': '创业板指',
        '000300.SS': '沪深300'
    }
    
    results = []
    for symbol, name in symbols.items():
        data = fetch_stock_data(symbol, None)
        if data:
            data['name'] = name
            results.append(data)
    
    print(f"✅ 获取 {len(results)} 支 A 股数据")
    return results


def fetch_fx_rates():
    """获取汇率数据"""
    print("💱 获取汇率数据...")
    
    # 使用 exchangerate-api.com（免费额度）或其他免费 API
    try:
        # 使用 Yahoo Finance 获取主要货币对
        pairs = {
            'USDCNY=X': '美元/人民币',
            'EURUSD=X': '欧元/美元',
            'USDJPY=X': '美元/日元',
            'GBPUSD=X': '英镑/美元',
            'USDKRW=X': '美元/韩元',
            'USDHKD=X': '美元/港币'
        }
        
        results = []
        for symbol, name in pairs.items():
            data = fetch_stock_data(symbol, None)
            if data:
                data['name'] = name
                results.append(data)
        
        print(f"✅ 获取 {len(results)} 个汇率数据")
        return results
    except Exception as e:
        print(f"⚠️  获取汇率失败: {e}")
        return []


def fetch_bond_yields():
    """获取债市收益率"""
    print("📊 获取债市数据...")
    
    # 使用 Yahoo Finance 获取国债收益率
    symbols = {
        '^TNX': '美国10年期国债',
        '^FVX': '美国5年期国债',
        '^TYX': '美国30年期国债'
    }
    
    results = []
    for symbol, name in symbols.items():
        data = fetch_stock_data(symbol, None)
        if data:
            data['name'] = name
            data['price'] = round(data['price'], 2)
            results.append(data)
    
    print(f"✅ 获取 {len(results)} 个债市数据")
    return results


def fetch_commodities():
    """获取大宗商品价格"""
    print("🛢️  获取大宗商品数据...")
    
    symbols = {
        'GC=F': '黄金',
        'CL=F': '原油(WTI)',
        'BZ=F': '原油(布伦特)',
        'SI=F': '白银',
        'HG=F': '铜',
        'NG=F': '天然气'
    }
    
    results = []
    for symbol, name in symbols.items():
        data = fetch_stock_data(symbol, None)
        if data:
            data['name'] = name
            results.append(data)
    
    print(f"✅ 获取 {len(results)} 个商品数据")
    return results


def fetch_crypto():
    """获取加密货币价格"""
    print("₿ 获取加密货币数据...")
    
    symbols = {
        'BTC-USD': '比特币',
        'ETH-USD': '以太坊'
    }
    
    results = []
    for symbol, name in symbols.items():
        data = fetch_stock_data(symbol, None)
        if data:
            data['name'] = name
            results.append(data)
    
    print(f"✅ 获取 {len(results)} 个加密货币数据")
    return results


def fetch_market_news():
    """获取市场新闻摘要（模拟或从免费源获取）"""
    print("📰 整理市场要闻...")
    
    # 这里可以使用 RSS 或免费新闻 API
    # 作为示例，返回一个占位符，实际应连接新闻 API
    news_summary = f"""
📅 {datetime.now().strftime('%Y年%m月%d日')} 全球市场概况

【美股】
- 关注美联储利率决议及鲍威尔讲话
- 科技股财报季持续，关注 AI 相关业绩
- 地缘政治风险对市场情绪的影响

【港股/A股】
- 关注南向资金流向及港股通动态
- 国内政策面变化及经济数据发布
- 中概股回归及港股 IPO 动态

【汇率/债市】
- 美元指数走势及主要货币对波动
- 全球主要央行货币政策分化
- 通胀数据对债市收益率的影响

【大宗商品】
- 原油价格受地缘政治和供需影响
- 黄金价格反映避险情绪变化
- 工业金属价格与经济周期关联
"""
    
    return news_summary


def save_market_data(data):
    """保存市场数据到文件"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"market_data_{timestamp}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    # 同时保存为最新文件
    with open('latest_market_data.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"💾 市场数据已保存: {filename}")
    return filename


def main():
    print("=" * 70)
    print("📊 全球市场数据收集")
    print("=" * 70)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 收集各类数据
    market_data = {
        'timestamp': datetime.now().isoformat(),
        'us_stocks': fetch_us_stocks(),
        'hk_stocks': fetch_hk_stocks(),
        'cn_stocks': fetch_cn_stocks(),
        'fx_rates': fetch_fx_rates(),
        'bonds': fetch_bond_yields(),
        'commodities': fetch_commodities(),
        'crypto': fetch_crypto(),
        'news_summary': fetch_market_news()
    }
    
    # 保存数据
    save_market_data(market_data)
    
    # 设置 GitHub Actions 输出
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"data_file=latest_market_data.json\n")
    
    print("\n✅ 市场数据收集完成")
    return 0


if __name__ == '__main__':
    sys.exit(main())
