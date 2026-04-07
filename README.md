# buffett-analysis — Claude Code Skill

> 用巴菲特 / 段永平价值投资框架，判断一家公司是否是好生意、当前是否值得建仓。

## 核心哲学

> 「我们是商业分析师，不是股票分析师。」——巴菲特  
> 「看不懂的不做。投资就是要找到一门好生意，然后等待好价格。」——段永平

**6关串行淘汰制**：任何一关 FAIL，立即输出 AVOID 结论并停止，不在坏公司上浪费时间。

## 6 关评估体系

| 关卡 | 核心问题 | FAIL 即终止 |
|------|---------|------------|
| 关卡1 看懂生意 | 能否清晰说明这家公司靠什么赚钱？ | ✅ |
| 关卡2 商业模式 | 消失测试：客户会不会很难受？FCF 是否为正？ | ✅ |
| 关卡3 护城河 | 什么阻止了有钱的竞争对手抢走市场份额？ | ✅ |
| 关卡4 管理层 | 这些人值得信任吗？他们像股东一样思考吗？ | ✅ |
| 关卡5 10年耐久性 | 10年后，这门生意比今天更好还是更差？ | ✅ |
| 关卡6 估值与建仓 | FCF Yield、归一化PE、安全边际是否合理？ | 🟢/🟡/🔴 |

## 支持市场

- **A股**：6位代码（如 `600519`）→ akshare 接口
- **港股**：5位代码（如 `00700`）→ akshare 港股接口
- **美股**：英文 ticker（如 `AAPL`）→ yfinance 接口

## 数据采集

通过 `fetch_data.py` 自动获取真实财务数据（不依赖搜索引擎）：

- 当前价格 & 总市值
- 近5年净利润 & 年度增速
- 毛利率趋势（近4-5期）
- 近5年 ROE
- 自由现金流（经营CF − 资本支出）近4年
- FCF Yield
- 归一化PE（近3-5年均值净利润）
- 分红/回购历史
- 前十大股东
- 资产负债率

## 安装与使用

### 1. 安装依赖

```bash
# A股/港股
pip3 install akshare pandas

# 美股（额外需要）
pip3 install yfinance
```

### 2. 安装 Skill

```bash
git clone https://github.com/lazywater-11/buffett-analysis-claude-skill.git \
  ~/.claude/skills/buffett-analysis
```

### 3. 使用方式

在 Claude Code 中：

```
/buffett-analysis 贵州茅台
/buffett-analysis 腾讯控股
/buffett-analysis Apple
```

或直接说：「用巴菲特框架分析一下 NVIDIA」

### 4. 直接运行数据采集脚本

```bash
python ~/.claude/skills/buffett-analysis/fetch_data.py --stock 600519 --name 贵州茅台
python ~/.claude/skills/buffett-analysis/fetch_data.py --stock 00700  --name 腾讯控股
python ~/.claude/skills/buffett-analysis/fetch_data.py --stock AAPL   --name Apple
```

## 分析报告自动存档

分析完成后，报告自动保存为 Markdown 文件到 Obsidian vault：

```
AI 证券分析/贵州茅台-600519-2026-04-07.md
```

包含：关卡总结、详细分析、财务数据摘录、后续跟踪建议。

## 与 stock-analysis 的区别

| Skill | 解决的问题 | 适用场景 |
|-------|-----------|---------|
| buffett-analysis | 值不值得投？（商业质量 + 估值逻辑）| 建仓前决策 |
| [stock-analysis](https://github.com/lazywater-11/stock-analysis-claude-skill) | 什么时候买？（技术面 + 趋势判断）| 择时参考 |

两者配合使用效果最佳：先判断好不好，再看时机对不对。

## License

MIT
