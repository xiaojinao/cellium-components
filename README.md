# Cellium Components Registry

组件市场的清单仓库。这里只放"组件说明"（`meta.json` + 可选的 `README.md`），**不放组件代码，也不收安装包**。组件代码和 zip 都放在你自己的仓库里，这里只登记它们在哪。

- 站点：https://components.cellium.top
- 官网：https://agent.cellium.top

## 两种提交方式

| 方式 | 适合谁 | 你要做什么 |
|---|---|---|
| **填 Issue 表单**（推荐） | 不想碰 git、不想手写 JSON | 打开「提交组件」Issue，填完提交，其余全自动 |
| **手工提 PR** | 想自己控制文件内容，或用 Git 拉取模式 | Fork 仓库改 `meta.json`，按下面流程提 PR |

### 方式一：填 Issue 表单

1. 打开 [新建 Issue → 提交组件](https://github.com/xiaojinao/cellium-components/issues/new?template=submit-component.yml)，会直接进入表单。
2. 按表单填写：组件名称、标识（slug）、一句话简介、分类、标签、作者、源码仓库、许可证、封面图、版本号、发布日期、安装包直链、最低 Agent 版本、更新日志、README。
3. 点提交，机器人会自动处理：
   - **校验**：必填项是否齐全、长度是否超限、slug 是否已被占用、版本号是否三段式、直链是否可下载（只探活，不下载）。
   - **通过**：生成 `components/<slug>/meta.json`（填了 README 会一并写 `components/<slug>/README.md`），创建 PR，并在 Issue 里给出链接。
   - **不通过**：评论列出问题并打上 `invalid` 标签。**直接编辑这个 Issue 再保存**即可自动重跑，不用重新开。
4. PR 合并后，Pages 会立即重建，线上站点最长 5 分钟更新。

几条规则：

- 一个 Issue 只提交一个组件；标识（slug）全站唯一，收录后不要改。
- 已收录的组件发新版：标识填原 slug、版本号填新版本。机器人会把新版本插到 `versions` 最前面，历史版本保留。
- 只改简介 / 分类 / 标签 / 封面 / README：同样开 Issue，版本号填**当前最新版本号**，机器人只更新元信息，不新增版本；完全没变化时不会产生 PR。
- 同一个版本号换包会被拒绝，必须提升版本号。构建只探活不下载，换包无法被发现，所以直接禁止。
- 安装包直链必须是 `https://`，通常是 GitHub Release 的附件地址，拿法见下面的 [「直链」是什么](#直链是什么)。
- 谁可以更新：标识一旦被某个 GitHub 账号提交，就只有那个账号（或该组件源码仓库的 owner）能再次更新，防止别人改你的组件信息或抢占标识。机器人在 `meta.json` 里记 `submitted_by` 作为凭证。
- 贡献归属：PR 里的 commit 直接以你（Issue 提交者）的 GitHub 身份作为 author，合并进 main 后自动记入你的贡献图；代他人提交时，在表单「作者名称」里填对方的 GitHub 用户名，会额外加一条 `Co-authored-by`，两个人都会被记为贡献者。
- 机器人只会写 `components/<slug>/` 下的 `meta.json` 和 `README.md`，不碰其它目录。
- 生成的文件会先用仓库自带的 `scripts/build.py --check` 兜底校验一次，不通过就回滚，不会产生半成品 PR。

表单方式只覆盖「直链」模式。想用 Git 拉取（`source` + `commit`），走下面的手工流程。

### 方式二：手工提 PR

1. 把组件打成 zip，作为一个版本上传到你仓库的 GitHub Releases（或任何能直接下载的地方）。
2. Fork 这个仓库，在 `components/` 下新建一个以组件标识命名的文件夹，里面放 `meta.json`（组件信息）和 `README.md`（详情页正文，可选但建议写）。`meta.json` 可以直接复制 [examples/example-cell.json](examples/example-cell.json) 改内容。
3. 本地校验：需要 Python 3.8 或更新版本（装了 Cellium Agent 就有，不需要额外依赖），在仓库根目录运行 `python scripts/build.py --check`（Linux/macOS 一般用 `python3`）。按提示改到通过。
4. 提 PR：提交 `components/<slug>/meta.json`（必需）和 `components/<slug>/README.md`（可选，不交则详情页没有正文），按 PR 模板填写信息。
5. 合并后，CI 会先校验；线上服务器每 5 分钟自动拉取并重新构建，最迟 5 分钟后组件出现在 https://components.cellium.top。

对应的 git 命令：

```bash
git clone https://github.com/<你的用户名>/cellium-components.git
cd cellium-components
mkdir -p components/my-cell
cp examples/example-cell.json components/my-cell/meta.json
touch components/my-cell/README.md
# Windows PowerShell 用：
# New-Item -ItemType Directory components/my-cell
# Copy-Item examples/example-cell.json components/my-cell/meta.json
# New-Item components/my-cell/README.md

# 然后编辑 components/my-cell/meta.json（组件信息）和 components/my-cell/README.md（详情页正文）
python scripts/build.py --check
# Linux/macOS 用：python3 scripts/build.py --check

git add components/my-cell/meta.json components/my-cell/README.md
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
  "cover": "https://raw.githubusercontent.com/you/cellium-my-cell/main/cover.png",
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
3. 在 `components/<slug>/` 下放 `meta.json`（填 zip 地址）和可选的 `README.md`，提 PR 到本仓库
4. 以后每发一版，重复第 2、3 步，在 `versions` 里加一条

构建时会做什么：

- 只访问一次这个地址、确认能打开（HTTP HEAD），**不下载文件，也不计算文件指纹**
- 打不开或返回错误（例如 404）→ CI 失败，并指出是哪个组件、哪个版本
- 能打开时，把文件大小（响应头 `content-length`）填进索引的 `size` 字段
- 因为不下载，**同一个版本号的内容被替换不会被发现**，所以别覆盖已经发布过的版本
- 本地网络不稳（TLS 握手被掐、超时）时加 `--skip-remote`，只校验格式不探活

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

构建时会 clone 你的公开仓库，按 `commit` 导出 `subdir` 目录、打 zip，并记录 zip 的 `sha256` 和 `size`。如果该目录里有 `README.md`，会显示在组件详情页；没有的话用 `components/<slug>/README.md` 兜底。

和直链相比：构建机每次都要拉仓库，慢一些；好处是你不用自己打包、也不会出现同版本号换包。

## `meta.json` 字段

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `slug` | 是 | 组件唯一标识，同时也是目录名。只能用小写字母、数字、`-`、`_`，2–40 字符 |
| `name` | 是 | 展示名，最多 60 字 |
| `summary` | 是 | 列表页的一句话介绍，最多 160 字；不要带换行或连续空格 |
| `category` | 是 | 只能从这 8 个里选：`web` `ai` `security` `interaction` `automation` `data` `media` `other` |
| `tags` | | 最多 8 个 |
| `author` | 是 | 作者名 |
| `repo` | | 源码仓库地址 |
| `license` | | 许可证，如 `MIT` |
| `cover` | | 封面图 https 地址，列表页和详情页展示；建议 16:9、≤300KB。不填则显示名称首字头像 |
| `deprecated` | | 填 `true` 表示已弃用 |
| `source` | | Git 拉取方式必填，直链方式不用 |
| `submitted_by` | | 由 Issue 机器人自动写入，**不要手填**；用于把组件更新权限绑定到原提交者 |
| `versions` | 是 | 至少一条，**最新版写在最前面** |

`versions` 里每一项：

| 字段 | 说明 |
| --- | --- |
| `version` | 必填，三段式数字，如 `1.2.3`（不接受 `v1.2.3`、`1.2`、`1.2.3-beta`） |
| `date` | 必填，格式 `2026-10-31` |
| `changelog` | 这一版改了什么，最多 500 字；不要带换行、连续空格或 PR 模板的勾选项 |
| `download` | 直链方式必填，安装包 https 地址 |
| `commit` / `ref` | Git 拉取方式用；`commit` 是一次提交的编号，`ref` 是 tag 或分支名 |
| `min_agent` | 需要的最低 Agent 版本 |
| `size` / `file` / `sha256` | 构建时自动回填，**不要手写** |

字段的机器可读定义在 [schema/meta.schema.json](schema/meta.schema.json)。

## 本地校验与构建

作者只需要跑校验；构建是 CI 和维护者的事。脚本只用 Python 标准库，不需要 `pip install`。

| 命令 | 谁用 | 做什么 |
| --- | --- | --- |
| `python scripts/build.py --check` | 作者自查 | 按构建规则检查所有 `meta.json`，并访问一次直链确认能打开 |
| `python scripts/build.py --check --skip-remote` | 作者、断网时 | 同上，但跳过直链探活；Git 拉取方式的组件仍需要联网拉仓库 |
| `python scripts/build.py` | CI、维护者 | 生成站点数据；不要在 PR 里提交 `dist/` |

Linux/macOS 上一般用 `python3` 代替 `python`。校验 Git 拉取方式的组件需要本机装好 `git`。

`python scripts/build.py` 的产物：

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
- **线上自动发布**：脚本在前端仓库 [`cellium-components-web`](https://github.com/xiaojinao/cellium-components-web)，不在本仓库。`scripts/deploy.sh` 由 crontab 每 5 分钟调用：`git pull` 前端 → 按需 `npm run build` → `node scripts/sync-data.mjs` 从 GitHub Pages 拉索引与详情 → 原子替换前端 `dist/data`、`dist/pkg`，nginx 直读 `dist`。镜像地址用 `CELLIUM_MIRROR` 覆盖。
  - 本仓库只负责生产数据（`build.py`），不参与线上发布
  - 服务器需要 **bash + Node 20+**；同步只走 Pages 域名，不直接探测组件直链
  - 查看：`crontab -l | grep deploy.sh`
  - 只更新组件数据时不会重新打包前端；只有 `dist/` 不存在或前端源码比 `dist/index.html` 新时才跑 `npm run build`
  - 需要构建前端但 `node_modules` 不存在时脚本直接失败，并提示先 `npm ci`
  - 拉取失败时保留旧数据，站点不会白屏，只是数据停在上一版
- **站点怎么读到数据**：前端只从同源取两个文件——`/data/index.json`（列表）和 `/data/c/<slug>.json`（详情），由 `sync-data.mjs` 写进前端 `dist/data/`。改了这个接口路径或字段名，`components.cellium.top` 会直接白屏。
- **GitHub Pages 已是线上站点的上游**：服务器从 Pages 拉数据，所以 Pages 构建失败时，线上站点会停在上一版（不白屏，但也不更新）。Pages 上那份带 `Access-Control-Allow-Origin: *`，第三方可直接抓取。
- **严格校验 vs 宽容发布**：PR 校验走严格模式（[.github/workflows/validate.yml](.github/workflows/validate.yml)），坏数据进不了 `main`；发布构建走宽容模式（[.github/workflows/pages.yml](.github/workflows/pages.yml) 用 `--tolerant`），单个组件坏了只跳过它并告警，不卡住整站发布。若所有组件都没通过校验，构建会拒绝发布空索引。

## 安全说明

进索引不等于审核过代码。直链方式的安装包内容由作者自己控制，同一个版本号可能被替换。安装前看一眼源码。

## 组件开发约定

- 单文件组件继承 `BaseCell`，暴露 `commands`
- 使用 `"admin"` 策略的组件必须实现 `is_policy_admin(platform_context)`，未实现时所有 admin 命令一律被拒绝
- 不要在 `is_policy_admin` 里抛异常，内部兜底返回 `False`
