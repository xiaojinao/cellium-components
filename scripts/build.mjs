#!/usr/bin/env node
// 构建组件索引：索引仓库只有 meta.json，源码在作者自己的仓库（Release 直链或 meta.source）
import { readdirSync, readFileSync, writeFileSync, mkdirSync, existsSync, rmSync, statSync, mkdtempSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { join, dirname, resolve } from 'node:path'
import { execFileSync } from 'node:child_process'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const COMPONENTS = join(ROOT, 'components')
const CACHE = join(ROOT, '.cache')
const OUT = process.argv.includes('--out')
  ? resolve(process.argv[process.argv.indexOf('--out') + 1])
  : join(ROOT, 'dist')
const CHECK_ONLY = process.argv.includes('--check')
const SKIP_REMOTE = process.argv.includes('--skip-remote') || process.env.CELLIUM_SKIP_REMOTE === '1'
// 宽容模式：坏组件只跳过并告警，不中断整站发布（线上部署用）
const TOLERANT = process.argv.includes('--tolerant')
const ALLOW_LOCAL_GIT = process.env.CELLIUM_ALLOW_LOCAL_GIT === '1'
const GIT_TIMEOUT = 180_000
const HTTP_TIMEOUT = 20_000

const errors = []
const badSlugs = new Set()
const fail = (slug, msg) => {
  errors.push(`${slug}: ${msg}`)
  badSlugs.add(slug)
}
const warn = (msg) => console.warn(`  ! ${msg}`)

const SEMVER = /^\d+\.\d+\.\d+$/
const cmp = (a, b) => {
  const pa = a.split('.').map(Number), pb = b.split('.').map(Number)
  for (let i = 0; i < 3; i++) if (pa[i] !== pb[i]) return pa[i] - pb[i]
  return 0
}
const sha256 = (buf) => createHash('sha256').update(buf).digest('hex')

const exec = (cmd, args, opts = {}) =>
  execFileSync(cmd, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], timeout: GIT_TIMEOUT, ...opts })

// ---------- Git 源（作者自己的仓库） ----------

// 只接受 https，避免索引仓库借 file:// 或 ssh 读取本机文件
function normalizeUrl(url) {
  const u = String(url || '').trim().replace(/\/+$/, '')
  if (/^https:\/\/[^\s]+$/i.test(u)) return u
  if (ALLOW_LOCAL_GIT && /^file:\/\//.test(u)) return u
  throw new Error(`source.url 必须是 https:// 的 Git 地址（当前: ${url}）`)
}

function mirrorPath(url) {
  return join(CACHE, 'git', createHash('sha1').update(url).digest('hex').slice(0, 16))
}

function syncMirror(url) {
  const dir = mirrorPath(url)
  if (existsSync(join(dir, 'HEAD'))) {
    try {
      exec('git', ['-C', dir, 'fetch', '--tags', '--prune', '--quiet', 'origin'])
    } catch {
      warn(`拉取失败，使用本地缓存：${url}`)
    }
    return dir
  }
  mkdirSync(dirname(dir), { recursive: true })
  exec('git', ['clone', '--mirror', '--quiet', url, dir])
  return dir
}

function resolveCommit(mirror, v) {
  const specs = [v.commit, v.ref, v.tag].filter(Boolean)
  if (!specs.length) throw new Error('git 版本必须提供 commit 或 ref')
  for (const s of specs) {
    try {
      return exec('git', ['-C', mirror, 'rev-parse', '--verify', `${s}^{commit}`]).trim()
    } catch { /* 试下一个 */ }
  }
  throw new Error(`找不到 commit/ref: ${specs.join(' / ')}`)
}

function exportTree(mirror, commit, subdir) {
  let clean = String(subdir || '').replace(/^\/+|\/+$/g, '')
  if (clean.split('/').includes('..')) throw new Error(`source.subdir 非法: ${subdir}`)
  const work = mkdtempSync(join(tmpdir(), 'cellium-src-'))
  const tar = join(work, 'src.tar')
  exec('git', ['-C', mirror, 'archive', '--format=tar', '--prefix=repo/', `--output=${tar}`, commit])
  exec('tar', ['-xf', tar, '-C', work])
  rmSync(tar, { force: true })
  const dir = clean ? join(work, 'repo', clean) : join(work, 'repo')
  if (!existsSync(dir) || !statSync(dir).isDirectory()) throw new Error(`source.subdir 不存在: ${clean || '.'}`)
  return dir
}

function zipDir(srcDir, outFile) {
  mkdirSync(dirname(outFile), { recursive: true })
  exec('zip', ['-q', '-r', outFile, '.',
    '-x', '*.pyc', '-x', '*__pycache__*', '-x', '.git/*', '-x', '*.DS_Store'], { cwd: srcDir })
}

// ---------- 远端直链（download 模式） ----------

// 只接受 https，避免索引里写 file:// 或内网地址
function normalizeDownload(url) {
  const u = String(url || '').trim()
  if (!/^https:\/\/[^\s]+$/i.test(u)) throw new Error(`download 必须是 https:// 直链（当前: ${url}）`)
  return u
}

// 只探活，不下载。返回 content-length（拿不到就是 undefined）
async function checkDownload(url) {
  if (SKIP_REMOTE) return undefined
  let res
  try {
    res = await fetch(url, {
      method: 'HEAD',
      redirect: 'follow',
      signal: AbortSignal.timeout(HTTP_TIMEOUT),
      headers: { 'user-agent': 'cellium-registry/1.0' },
    })
  } catch (e) {
    throw new Error(`下载地址不可达: ${e.cause?.code || e.message}`)
  }
  if (!res.ok) throw new Error(`下载地址返回 ${res.status}（${url}）`)
  const len = Number(res.headers.get('content-length') || 0)
  return len > 0 ? len : undefined
}

// ---------- 遍历组件 ----------

const slugs = new Set()
const items = []
const catCount = {}

async function main() {
for (const dir of readdirSync(COMPONENTS).sort()) {
  const base = join(COMPONENTS, dir)
  if (!statSync(base).isDirectory()) continue
  const metaPath = join(base, 'meta.json')
  if (!existsSync(metaPath)) { fail(dir, '缺少 meta.json'); continue }
  // 索引仓库只收元信息，组件源码必须留在作者自己的仓库
  if (existsSync(join(base, 'src'))) { fail(dir, '索引仓库不接受组件源码，请删除 components/<slug>/src'); continue }

  let meta
  try { meta = JSON.parse(readFileSync(metaPath, 'utf8')) } catch (e) { fail(dir, `meta.json 解析失败: ${e.message}`); continue }

  for (const k of ['slug', 'name', 'summary', 'category', 'author']) {
    if (!meta[k] || typeof meta[k] !== 'string') fail(dir, `缺少或非法字段 ${k}`)
  }
  if (meta.slug !== dir) fail(dir, `slug (${meta.slug}) 必须与目录名 (${dir}) 一致`)
  if (!/^[a-z0-9][a-z0-9_-]{1,39}$/.test(meta.slug || '')) fail(dir, 'slug 只能是小写字母/数字/中划线/下划线，2-40 位')
  if (slugs.has(meta.slug)) fail(dir, `slug 重复: ${meta.slug}`)
  slugs.add(meta.slug)
  if (meta.name && meta.name.length > 60) fail(dir, 'name 超过 60 字')
  if (meta.summary && meta.summary.length > 160) fail(dir, 'summary 超过 160 字')
  if (!Array.isArray(meta.tags)) meta.tags = []
  if (meta.tags.length > 8) fail(dir, 'tags 最多 8 个')

  if (!Array.isArray(meta.versions) || meta.versions.length === 0) { fail(dir, 'versions 至少一个'); continue }

  // 版本自带 download 直链时不碰任何源码；只有需要现打包的版本才解析 source
  const needsSource = meta.versions.some((v) => !v.download)
  const isGit = needsSource && !!(meta.source && meta.source.type === 'git')
  let mirror = null
  if (needsSource && meta.source) {
    if (meta.source.type !== 'git') fail(dir, `source.type 目前只支持 "git"`)
    if (!meta.source.url) fail(dir, 'source.url 必填')
    else {
      try {
        meta.source.url = normalizeUrl(meta.source.url)
        mirror = syncMirror(meta.source.url)
      } catch (e) { fail(dir, e.message) }
    }
  }

  const seen = new Set()
  const versions = []
  let readme = ''

  for (const v of meta.versions) {
    if (!SEMVER.test(v.version || '')) fail(dir, `版本号非法: ${v.version}`)
    if (seen.has(v.version)) fail(dir, `版本重复: ${v.version}`)
    seen.add(v.version)
    if (!/^\d{4}-\d{2}-\d{2}$/.test(v.date || '')) fail(dir, `版本 ${v.version} 日期格式应为 YYYY-MM-DD`)

    // 直链模式：不 clone、不打包，只 HEAD 探活
    if (v.download) {
      try {
        const url = normalizeDownload(v.download)
        const size = await checkDownload(url)
        versions.push({ ...v, download: url, size })
      } catch (e) {
        fail(dir, `版本 ${v.version} ${e.message}`)
      }
      continue
    }

    if (isGit) {
      try {
        if (!mirror) throw new Error('源仓库不可用')
        const commit = resolveCommit(mirror, v)
        const srcDir = exportTree(mirror, commit, meta.source.subdir)
        if (!readme && existsSync(join(srcDir, 'README.md'))) readme = readFileSync(join(srcDir, 'README.md'), 'utf8')
        versions.push({ ...v, commit, file: `${meta.slug}-${v.version}.zip`, _srcDir: srcDir })
      } catch (e) {
        fail(dir, `拉取 ${v.version} 失败: ${e.message}`)
      }
      continue
    }

    fail(dir, `版本 ${v.version} 缺少 download 直链或 source`)
  }

  // 直链模式没有源码目录可读，允许 components/<slug>/README.md 作为详情页正文
  if (!readme) {
    const localReadme = join(base, 'README.md')
    if (existsSync(localReadme)) readme = readFileSync(localReadme, 'utf8')
  }

  versions.sort((a, b) => cmp(b.version, a.version))
  if (versions.length > 1) {
    const sorted = [...versions].map((v) => v.version)
    if (cmp(sorted[0], sorted[sorted.length - 1]) <= 0) fail(dir, '版本号未按递增填写')
  }

  if (TOLERANT && badSlugs.has(dir)) { warn(`跳过 ${dir}（校验未通过）`); continue }

  const latest = versions[0]

  items.push({
    slug: meta.slug,
    name: meta.name,
    summary: meta.summary,
    category: meta.category,
    tags: meta.tags,
    author: meta.author,
    repo: meta.repo || (meta.source && meta.source.url) || '',
    license: meta.license || '',
    deprecated: !!meta.deprecated,
    source: meta.source || null,
    latest_version: latest?.version || '',
    updated_at: latest?.date || '',
    versions: versions.map(({ _srcDir, ...rest }) => rest),
    readme,
    _versions: versions,
  })
  catCount[meta.category] = (catCount[meta.category] || 0) + 1
}

if (errors.length) {
  const lines = errors.map((e) => '  - ' + e).join('\n')
  if (!TOLERANT) {
    console.error(`\n✗ 校验失败（${errors.length} 项）:\n${lines}\n`)
    process.exit(1)
  }
  console.warn(`\n! 已跳过 ${badSlugs.size} 个组件（${errors.length} 项问题）:\n${lines}\n`)
}

console.log(`✓ 校验通过：${items.length} 个组件，${items.reduce((n, i) => n + i.versions.length, 0)} 个版本`)
if (CHECK_ONLY) process.exit(0)

// ---------- 输出 ----------
rmSync(join(OUT, 'data'), { recursive: true, force: true })
rmSync(join(OUT, 'pkg'), { recursive: true, force: true })
mkdirSync(join(OUT, 'data', 'c'), { recursive: true })
mkdirSync(join(OUT, 'pkg'), { recursive: true })

// 先打包（回填 sha256/size），再写索引，保证索引里的校验值可用
for (const item of items) {
  for (const v of item._versions) {
    if (v.download) continue   // 直链版本不打本地包
    const outZip = join(OUT, 'pkg', `${item.slug}-${v.version}.zip`)
    try {
      zipDir(v._srcDir, outZip)
      const buf = readFileSync(outZip)
      v.sha256 = sha256(buf)
      v.size = buf.length
    } catch (e) {
      warn(`打包失败 ${item.slug}@${v.version}: ${e.message}`)
    }
  }
  item.versions = item._versions.map(({ _srcDir, ...rest }) => rest)
}

const index = {
  generated_at: new Date().toISOString().slice(0, 19).replace('T', ' '),
  count: items.length,
  categories: Object.entries(catCount).map(([key, count]) => ({ key, count })).sort((a, b) => b.count - a.count),
  items: items
    .map(({ readme, _versions, ...rest }) => rest)
    .sort((a, b) => (a.updated_at < b.updated_at ? 1 : a.updated_at > b.updated_at ? -1 : 0)),
}
writeFileSync(join(OUT, 'data', 'index.json'), JSON.stringify(index, null, 2))

for (const item of items) {
  const detail = {
    slug: item.slug,
    name: item.name,
    summary: item.summary,
    category: item.category,
    tags: item.tags,
    author: item.author,
    repo: item.repo,
    license: item.license,
    deprecated: item.deprecated,
    source: item.source,
    latest_version: item.latest_version,
    updated_at: item.updated_at,
    readme: item.readme,
    versions: item.versions,
  }
  writeFileSync(join(OUT, 'data', 'c', `${item.slug}.json`), JSON.stringify(detail, null, 2))
}

console.log(`✓ 输出到 ${OUT}`)
console.log('  data/index.json  data/c/*.json  pkg/*.zip')

}

main().catch((e) => {
  console.error(`\n✗ 构建失败: ${e.message}\n`)
  process.exit(1)
})
