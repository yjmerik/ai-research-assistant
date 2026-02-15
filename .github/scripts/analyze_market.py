#!/usr/bin/env python3
"""
使用 AI 分析市场数据

使用 Kimi API 生成市场分析报告
"""

import os
import sys
import json
import urllib.request
import urllib.error

# Kimi API 配置
KIMI_API_BASE = "https://api.moonshot.cn/v1"


class MarketAnalyzer:
    """市场分析器"""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.environ.get('KIMI_API_KEY')
    
    def _request(self, endpoint, data):
        """发送 HTTP 请求"""
        url = f"{KIMI_API_BASE}{endpoint}"
        
        headers = {
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
        req = urllib.request.Request(url, data=json_data, headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            print(f"HTTP Error {e.code}: {error_body}")
            return {'error': error_body}
        except Exception as e:
            return {'error': str(e)}
    
    def analyze_market(self, market_data):
        """分析市场数据"""
        print("🤖 使用 Kimi AI 分析市场数据...")
        
        prompt = self._build_analysis_prompt(market_data)
        
        data = {
            "model": "moonshot-v1-8k",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一位专业的金融分析师，擅长全球市场分析。请提供简洁、专业的市场解读，帮助投资者快速了解市场动态。"
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 4000
        }
        
        result = self._request('/chat/completions', data)
        
        if 'error' in result:
            print(f"❌ API 错误: {result['error']}")
            return None
        
        try:
            content = result['choices'][0]['message']['content']
            return content
        except Exception as e:
            print(f"❌ 解析失败: {e}")
            return None
    
    def _build_analysis_prompt(self, data):
        """构建分析提示词"""
        from datetime import datetime
        
        prompt = f"""请对以下 {datetime.now().strftime('%Y年%m月%d日')} 全球市场数据进行分析，生成一份专业的市场日报。

## 原始数据

### 美股主要指数
"""
        
        for stock in data.get('us_stocks', [])[:4]:
            change_emoji = "📈" if stock.get('change', 0) >= 0 else "📉"
            prompt += f"- {stock['name']} ({stock['symbol']}): {stock['price']} ({stock['change']:+.2f}, {stock['change_pct']:+.2f}%) {change_emoji}\n"
        
        prompt += "\n### 港股主要指数\n"
        for stock in data.get('hk_stocks', [])[:4]:
            change_emoji = "📈" if stock.get('change', 0) >= 0 else "📉"
            prompt += f"- {stock['name']} ({stock['symbol']}): {stock['price']} ({stock['change']:+.2f}, {stock['change_pct']:+.2f}%) {change_emoji}\n"
        
        prompt += "\n### A股主要指数\n"
        for stock in data.get('cn_stocks', [])[:4]:
            change_emoji = "📈" if stock.get('change', 0) >= 0 else "📉"
            prompt += f"- {stock['name']} ({stock['symbol']}): {stock['price']} ({stock['change']:+.2f}, {stock['change_pct']:+.2f}%) {change_emoji}\n"
        
        prompt += "\n### 主要汇率\n"
        for fx in data.get('fx_rates', []):
            prompt += f"- {fx['name']}: {fx['price']:.4f} ({fx['change_pct']:+.2f}%)\n"
        
        prompt += "\n### 债市收益率\n"
        for bond in data.get('bonds', []):
            prompt += f"- {bond['name']}: {bond['price']:.2f}%\n"
        
        prompt += "\n### 大宗商品\n"
        for comm in data.get('commodities', []):
            change_emoji = "📈" if comm.get('change', 0) >= 0 else "📉"
            prompt += f"- {comm['name']}: {comm['price']:.2f} ({comm['change_pct']:+.2f}%) {change_emoji}\n"
        
        prompt += "\n### 加密货币\n"
        for crypto in data.get('crypto', []):
            change_emoji = "📈" if crypto.get('change', 0) >= 0 else "📉"
            prompt += f"- {crypto['name']}: ${crypto['price']:,.2f} ({crypto['change_pct']:+.2f}%) {change_emoji}\n"
        
        prompt += f"""
### 市场要闻
{data.get('news_summary', '暂无新闻摘要')}

---

请按照以下格式输出分析报告：

# 📊 {datetime.now().strftime('%Y年%m月%d日')} 全球市场日报

## 🎯 核心要点（3-5条）
用 bullet points 列出今日市场最重要的变化

## 🇺🇸 美股分析
- 主要指数表现
- 涨跌原因分析
- 关键个股动态
- 技术面简评

## 🇭🇰 港股/A股分析
- 港股市场综述
- A股主要指数表现
- 中概股动态
- 南向资金流向

## 💱 汇率与债市
- 美元指数及主要货币对走势
- 美债收益率变化及影响
- 人民币汇率分析

## 🛢️ 大宗商品
- 原油、黄金、铜等表现
- 价格变动原因
- 与股市的关联

## ₿ 加密货币
- 比特币、以太坊走势
- 与风险资产的相关性

## 📈 明日关注
- 重要经济数据发布
- 央行政策动向
- 财报季重点
- 风险提示

## 💡 投资建议（仅供参考）
- 短期策略建议
- 风险提醒

要求：
1. 使用中文，语言专业但易懂
2. 适当使用 emoji 增强可读性
3. 分析要有深度，不只罗列数据
4. 控制篇幅在 2000 字以内
5. 最后加上免责声明
"""
        
        return prompt


def load_market_data():
    """加载市场数据"""
    try:
        with open('latest_market_data.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        pass
    
    import glob
    files = glob.glob('market_data_*.json')
    if files:
        latest = max(files, key=os.path.getctime)
        with open(latest, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    return None


def save_report(report):
    """保存分析报告"""
    from datetime import datetime
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"market_report_{timestamp}.md"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 同时保存为最新文件
    with open('latest_market_report.md', 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"💾 分析报告已保存: {filename}")
    return filename


def main():
    print("=" * 70)
    print("📈 AI 市场分析")
    print("=" * 70)
    
    # 获取环境变量
    api_key = os.environ.get('KIMI_API_KEY')
    if not api_key:
        print("❌ 缺少 KIMI_API_KEY 环境变量")
        return 1
    
    # 加载市场数据
    data = load_market_data()
    if not data:
        print("❌ 没有找到市场数据")
        return 1
    
    print(f"📊 数据时间: {data.get('timestamp', 'N/A')}")
    print()
    
    # 创建分析器
    analyzer = MarketAnalyzer(api_key)
    
    # 分析市场
    report = analyzer.analyze_market(data)
    
    if report:
        print("\n" + "=" * 70)
        print("📄 报告预览")
        print("=" * 70)
        preview = report[:800] + "..." if len(report) > 800 else report
        print(preview)
        print()
        
        # 保存报告
        filename = save_report(report)
        
        # 设置 GitHub Actions 输出
        github_output = os.environ.get('GITHUB_OUTPUT')
        if github_output:
            with open(github_output, 'a') as f:
                f.write(f"report_file=latest_market_report.md\n")
                f.write(f"report_length={len(report)}\n")
        
        print("✅ 市场分析完成")
        return 0
    else:
        print("❌ 分析失败")
        return 1


if __name__ == '__main__':
    sys.exit(main())
