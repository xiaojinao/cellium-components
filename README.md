# Cellium Components Registry

组件市场的索引仓库。索引里只有 JSON，源码在作者自己的仓库。

- 站点：https://components.cellium.top
- 官网：https://agent.cellium.top

## 三种来源

| 模式 | 索引仓库里放什么 | 源码在哪 | 构建时做什么 |
|---|---|---|---|
| **直链**（推荐给外部作者） | `meta.json` | 作者仓库的 Release 附件 | 只发 HEAD 请求查可达，不下载、不打包 |
| **本地源码**（官方组件） | `meta.json` + `src/` | 本仓库 | 打 zip |
| **Git 拉取**（可选） | `meta.json` | 作者仓库的某个 commit | clone、按 commit 导出、打 zip |

## 直链模式：只写一个 JSON

这条路径下，索引仓库里**没有任何代码**，只有元信息。

```
components/<slug>/
└── meta.json
```

```json
{
  "slug": "my-cell",
  "name": "我的组件",
  "summary": "一句话说明组件做什么",
  "category": "automation",
  "tags": ["tts", "语音"],
  "author": "your-name",
  "repo": "https://github.com/you/cellium-my-cell",
  "license": "MIT",
  "versions": [
    {
      "version": "1.0.0",
      "date": "2026-10-31",
      "changelog": "首个版本",
      "download": "https://github.com/you/cellium-my-cell/releases/download/v1.0.0/my-cell.zip"
    }
  ]
}
```

作者流程：

1. 写插件，仓库结构 `src/<name>.py` 或根目录直接放 `.py`
2. 打包成 zip，发到自己的 Release
3. 把 zip 直链和描述提 PR 到本仓库
4. 发版就重复 2–3

构建时只会对 `download` 发一个 HTTP HEAD：

- 非 2xx → 构建失败，明确报出是哪个组件哪个版本
- `content-length` 会被回填到索引的 `size` 字段
- **不下载文件，不算 hash**，所以直链内容变了构建不会知道

`download` 必须是 `https://`。`file://`、`http://`、内网地址会被拒绝。

## 本地源码模式（官方组件）

```
components/<slug>/
├── meta.json
├── README.md      # 详情页正文
└── src/
    └── <name>.py
```

版本里写 `file` 指向源码相对路径，构建打出 `pkg/<slug>-<version>.zip` 并回填 `sha256` / `size`。

## Git 拉取模式（可选）

```json
{
  "source": { "type": "git", "url": "https://github.com/you/repo", "subdir": "component" },
  "versions": [{ "version": "1.0.0", "date": "2026-10-31", "commit": "9f2c1ab..." }]
}
```

`commit` 优先，其次是 `ref`（tag/分支）。镜像缓存在 `.cache/git/`，增量 fetch。只接受 `https://`。

## meta.json 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `slug` | ✅ | 小写字母/数字/`-`/`_`，2–40 位，与目录名一致 |
| `name` | ✅ | 展示名，≤ 60 字 |
| `summary` | ✅ | 列表页摘要，≤ 160 字 |
| `category` | ✅ | `web` `ai` `security` `interaction` `automation` `data` `media` `other` |
| `tags` | | 最多 8 个 |
| `author` | ✅ | 作者名 |
| `repo` | | 源码仓库 |
| `license` | | 许可证标识 |
| `deprecated` | | 标记弃用 |
| `source` | | Git 模式必填 |
| `versions[]` | ✅ | 至少一项，版本递增，最新版在前 |

`versions[]`：

| 字段 | 说明 |
| --- | --- |
| `version` | ✅ 语义化版本 `x.y.z` |
| `date` | ✅ `YYYY-MM-DD` |
| `changelog` | ≤ 500 字 |
| `download` | 直链模式必填，安装包 https 直链 |
| `size` | 可选，构建自动回填 |
| `file` | 本地源码模式必填 |
| `commit` / `ref` | Git 模式用 |
| `min_agent` | 最低 Agent 版本 |

Schema 见 `schema/meta.schema.json`。

## 构建

```bash
npm run validate        # 校验，会发 HEAD 请求查直链
npm run validate:local  # 校验，跳过网络请求（离线用）
npm run build           # 输出 dist/data/*.json 与 dist/pkg/*.zip
```

产物：

- `dist/data/index.json` — 列表页数据
- `dist/data/c/<slug>.json` — 详情页数据
- `dist/pkg/<slug>-<version>.zip` — 仅本地源码/Git 模式才有

纯直链组件的仓库，构建产物只有 JSON，没有 `pkg/`。

## 自动发布

线上服务器 crontab 每 5 分钟执行 `scripts/deploy.sh`：`git pull` → 构建 → 前端打包。nginx 直读 `frontend/dist`。

```bash
crontab -l | grep deploy.sh
```

直链是死的那一刻，下一次部署就会失败。想避免全站卡住，把 `deploy.sh` 里的构建失败改成告警而非中止。

## 安全说明

进索引不等于审核过代码。直链模式的安装包内容由作者自己控制，同版本号可能被替换。安装前看一眼源码。

## 组件开发约定

- 单文件组件继承 `BaseCell`，暴露 `commands`
- 使用 `"admin"` 策略的组件必须实现 `is_policy_admin(platform_context)`，未实现时所有 admin 命令一律被拒绝
- 不要在 `is_policy_admin` 里抛异常，内部兜底返回 `False`
