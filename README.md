# Cellium Components Registry

组件市场的清单仓库。这里只放"组件说明"（一堆 JSON），**不放组件代码，也不收安装包**。组件代码和 zip 都放在你自己的仓库里，这里只登记它们在哪。

- 站点：https://components.cellium.top
- 官网：https://agent.cellium.top

## 三分钟走通一次提交

1. 把组件打成 zip，作为一个版本上传到你仓库的 GitHub Releases（或任何能直接下载的地方）。
2. Fork 这个仓库，在 `components/` 下新建一个以组件标识命名的文件夹，里面放一个 `meta.json`。可以直接复制 [examples/example-cell.json](examples/example-cell.json) 改内容。
3. 本地校验：装 Node 18 或更新版本，在仓库根目录运行 `npm run validate`（不需要 `npm install`，脚本只用 Node 自带模块）。按提示改到通过。
4. 提 PR：只提交 `components/<slug>/meta.json` 这一个文件，按 PR 模板填写信息。
5. 合并后，CI 会先校验；线上服务器每 5 分钟自动拉取并重新构建，最迟 5 分钟后组件出现在 https://components.cellium.top。

对应的 git 命令：

```bash
git clone https://github.com/<你的用户名>/cellium-components.git
cd cellium-components
mkdir -p components/my-cell
cp examples/example-cell.json components/my-cell/meta.json
# Windows PowerShell 用：
# New-Item -ItemType Directory components/my-cell
# Copy-Item examples/example-cell.json components/my-cell/meta.json

# 然后编辑 components/my-cell/meta.json，把内容改成你的组件
npm run validate

git add components/my-cell/meta.json
git commit -m "add component: my-cell"
git push
```

推完在 GitHub 页面上点 “Compare & pull request” 发起 PR。

## 两种登记方式

| 方式 | 你要提供什么 | 源码在哪 | 构建时做什么 |
|---|---|---|---|
| **直链**（推荐） | 一个 zip 的下载地址 | 你自己的仓库 Release 附件 | 只访问一次地址确认能打开，不下载、不打包 |
| **Git 拉取**（可选） | 仓库地址 + 提交编号 | 你自己仓库的某次提交 | 拉取仓库、按提交导出、打成 zip |

## “直链”是什么

“直链”是行话，指**用浏览器打开就会直接开始下载文件（zip）的 https 地址**，通常就是 GitHub Releases 里附件的地址，形如：

```
https://github.com/you/cellium-example/releases/download/v1.0.0/example-cell.zip
```

它不是仓库首页，也不是网页地址。在 GitHub 上的拿法：打开你的仓库，点右侧 **Releases** → 进入某个版本 → 在附件上右键 → 复制链接地址。

## 方式一：直链（推荐）

这个方式下，本仓库里**没有任何代码**，只有元信息：

```
components/<slug>/
├── meta.json
└── README.md      # 可选，放了就会显示在组件详情页
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

1. 写组件，仓库结构 `src/<name>.py`，或根目录直接放 `.py`
2. 打包成 zip，发到你自己的 Release
3. 把 zip 下载地址和描述提 PR 到本仓库
4. 以后每发一版，重复第 2、3 步，在 `versions` 里加一条

构建时会做什么：

- 只访问一次这个地址、确认能打开（HTTP HEAD），**不下载文件，也不计算文件指纹**
- 打不开或返回错误（例如 404）→ CI 失败，并指出是哪个组件、哪个版本
- 能打开时，把文件大小（响应头 `content-length`）填进索引的 `size` 字段
- 因为不下载，**同一个版本号的内容被替换不会被发现**，所以别覆盖已经发布过的版本

`download` 必须是 `https://`。`file://`、`http://`、内网地址会被拒绝。

## 方式二：Git 拉取（可选）

你不自己打 zip，只告诉我们要从哪拉：

```json
{
  "source": { "type": "git", "url": "https://github.com/you/repo", "subdir": "component" },
  "versions": [{ "version": "1.0.0", "date": "2026-10-31", "commit": "9f2c1ab..." }]
}
```

- `subdir` 是组件在仓库里的目录，留空表示仓库根目录
- 每个版本填 `commit`（一次提交的 40 位编号，不会变）最稳；也可以填 `ref`（tag 或分支名），但 tag 和分支会移动，同一个版本号可能指向不同代码
- 只接受 `https://` 的仓库地址
- 构建机器会缓存仓库到 `.cache/git/`，之后只增量拉取

构建时会 clone 你的公开仓库，按 `commit` 导出 `subdir` 目录、打 zip，并记录 zip 的 `sha256` 和 `size`。如果该目录里有 `README.md`，会显示在组件详情页。

和直链相比：构建机每次都要拉仓库，慢一些；好处是你不用自己打包、也不会出现同版本号换包。

## `meta.json` 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `slug` | 是 | 组件唯一标识，同时也是目录名。只能用小写字母、数字、`-`、`_`，2–40 字符 |
| `name` | 是 | 展示名，最多 60 字 |
| `summary` | 是 | 列表页的一句话介绍，最多 160 字 |
| `category` | 是 | 只能从这 8 个里选：`web` `ai` `security` `interaction` `automation` `data` `media` `other` |
| `tags` | | 最多 8 个 |
| `author` | 是 | 作者名 |
| `repo` | | 源码仓库地址 |
| `license` | | 许可证，如 `MIT` |
| `deprecated` | | 填 `true` 表示已弃用 |
| `source` | | Git 拉取方式必填，直链方式不用 |
| `versions` | 是 | 至少一条，**最新版写在最前面** |

`versions` 里每一项：

| 字段 | 说明 |
| --- | --- |
| `version` | 必填，三段式数字，如 `1.2.3`（不接受 `v1.2.3`、`1.2`、`1.2.3-beta`） |
| `date` | 必填，格式 `2026-10-31` |
| `changelog` | 这一版改了什么，最多 500 字 |
| `download` | 直链方式必填，安装包 https 地址 |
| `commit` / `ref` | Git 拉取方式用；`commit` 是一次提交的编号，`ref` 是 tag 或分支名 |
| `min_agent` | 需要的最低 Agent 版本 |
| `size` / `file` / `sha256` | 构建时自动回填，**不要手写** |

字段的机器可读定义在 [schema/meta.schema.json](schema/meta.schema.json)。

## 本地校验与构建

作者只需要跑校验；构建是 CI 和维护者的事。

| 命令 | 谁用 | 做什么 |
| --- | --- | --- |
| `npm run validate` | 作者自查 | 按构建规则检查所有 `meta.json`，并访问一次直链确认能打开 |
| `npm run validate:offline` | 作者、断网时 | 同上，但不访问网络，直链只检查格式 |
| `npm run build` | CI、维护者 | 生成站点数据；不要在 PR 里提交 `dist/` |

`npm run build` 的产物：

- `dist/data/index.json` — 列表页数据
- `dist/data/c/<slug>.json` — 详情页数据
- `dist/pkg/<slug>-<version>.zip` — 只有 Git 拉取方式才有

纯直链的仓库，产物只有 JSON，没有 `pkg/`。

## 维护者须知（提交组件的作者可以跳过）

- **GitHub Pages**：在仓库 **Settings → Pages → Source** 选 **GitHub Actions**（配置一次）。之后每次 push 到 `main`，[.github/workflows/pages.yml](.github/workflows/pages.yml) 会构建并把整个 `dist/` 发布到 Pages：
  - `https://xiaojinao.github.io/cellium-components/data/index.json`
  - `https://xiaojinao.github.io/cellium-components/data/c/<slug>.json`
  - `https://xiaojinao.github.io/cellium-components/pkg/<slug>-<version>.zip`（仅 Git 拉取方式）
  - Pages 走 CDN，更新后可能有几分钟延迟；线上站点 `components.cellium.top` 始终是最新
- **线上自动发布**：服务器 crontab 每 5 分钟跑一次 [scripts/deploy.sh](scripts/deploy.sh)，流程是 `git pull` 注册表 → `git pull` 前端仓库 → 构建索引 → 把 JSON 直接写进前端 `dist/`，nginx 直读 `dist`。前端默认在仓库同级目录 `cellium-components-web`，可用环境变量 `CELLIUM_SITE_DIR` 覆盖。
  - 查看：`crontab -l | grep deploy.sh`
  - 数据是运行时 `fetch` 的静态文件，所以**只更新组件数据时不会重新打包前端**；只有 `dist/` 不存在或前端源码比 `dist/index.html` 新时才跑 `npm run build`
  - 需要构建但 `node_modules` 不存在时脚本直接失败，并提示先 `npm ci`，避免假装发布成功
  - 部署用的是宽容模式：坏掉的组件会被跳过并告警，不会卡住整站发布
- **站点怎么读到数据**：前端只从同源取两个文件——`/data/index.json`（列表）和 `/data/c/<slug>.json`（详情），这两个文件由 `deploy.sh` 写进前端 `dist/data/`。改了这个接口路径或字段名，`components.cellium.top` 会直接白屏。
- **GitHub Pages 是镜像**：Pages 上那份是同一套 JSON 的公开副本，带 `Access-Control-Allow-Origin: *`，方便第三方直接抓取；站点前端不用它。Pages 构建是严格的，直链坏了会导致 Pages 部署失败，但线上站点仍会靠 `--tolerant` 继续发布。

## 安全说明

进索引不等于审核过代码。直链方式的安装包内容由作者自己控制，同一个版本号可能被替换。安装前看一眼源码。

## 组件开发约定

- 单文件组件继承 `BaseCell`，暴露 `commands`
- 使用 `"admin"` 策略的组件必须实现 `is_policy_admin(platform_context)`，未实现时所有 admin 命令一律被拒绝
- 不要在 `is_policy_admin` 里抛异常，内部兜底返回 `False`
