# Tavily AI 搜索（Cellium 组件）

把 [Tavily](https://tavily.com) 的 AI 搜索能力接进 Cellium Agent，返回结构化结果，方便 Agent 直接消费。

## 特性

- **search**：AI 增强搜索，可选 `include_answer` 直接拿总结答案
- **search_news**：按天范围检索新闻
- **extract**：给定 URL 提取网页正文
- **crawl**：按深度爬取站点多个页面
- **Token 安全**：结果数与正文长度强制截断，避免撑爆上下文
- **零内置凭据**：组件不携带任何 API Key，由使用者自行配置

## 安装

在 Cellium Agent 中执行：

```
component market_install slug=tavily-search
```

或从组件市场页面点击安装。

## 配置 API Key

组件依赖 `tavily-python`：

```
pip install tavily-python
```

然后二选一配置 Key（在 [tavily.com](https://tavily.com) 免费申请）：

**方式一：命令写入**

```
tavily_search command=config args="tvly-你的key"
```

**方式二：环境变量**

```
export TAVILY_API_KEY=tvly-你的key
```

配置会写入 `config/tavily.yaml`，查看当前配置（自动脱敏）：

```
tavily_search command=config
```

## 命令一览

| 命令 | 说明 | 主要参数 |
|---|---|---|
| `search` | AI 增强搜索 | `query`, `max_results`≤5, `search_depth`, `include_answer`, `topic` |
| `search_news` | 新闻搜索 | `query`, `max_results`≤5, `days`≤7 |
| `extract` | 网页正文提取 | `urls`≤3，单页≤8000字符 |
| `crawl` | 站点爬取 | `url`, `max_depth`≤2, `limit`≤10 |
| `config` | 查看/设置 Key | `args="tvly-xxxx"` |
| `help` | 帮助 | `topic` |

## 示例

```
tavily_search command=search args="掌阅科技 涨停"
tavily_search command=search args={"query":"AI 短剧","max_results":5,"include_answer":true}
tavily_search command=search_news args={"query":"具身智能","days":3}
tavily_search command=extract args="https://example.com"
tavily_search command=crawl args={"url":"https://example.com","max_depth":1,"limit":5}
```

## Token 安全限制

| 命令 | 限制 |
|---|---|
| search | 最多 5 条，每条 500 字符 |
| search_news | 最多 5 条，每条 500 字符 |
| extract | 最多 3 个 URL，单页 8000，总计 20000 字符 |
| crawl | 深度≤2，最多 10 页，单页 5000，总计 30000 字符 |

## 许可证

MIT
